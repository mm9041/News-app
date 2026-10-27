"""基于 Redis 的滑动窗口限流。

固定窗口（INCR + EXPIRE）有个经典缺陷：窗口边界处可以瞬间打出 2 倍流量 ——
上一个窗口末尾打 10 次、新窗口开头再打 10 次，两次都合法。
滑动窗口用 ZSET 存每次请求的时间戳：ZREMRANGEBYSCORE 清掉窗口外的，
ZCARD 数出真实窗口内的请求数，没有边界问题。

判断与写入放在**同一段 Lua** 里执行：两次往返之间并发请求会互相错判，
且 ZSET 的 member 必须唯一（用纳秒时间戳），否则同毫秒请求会互相覆盖。

Redis 不可用时一律放行：限流是保护措施，不能因为它自己挂了就把业务拦死。
"""

import time

from fastapi import HTTPException, Request, status

from config.cache_conf import redis_client
from utils.logger import get_logger

logger = get_logger(__name__)

RATE_PREFIX = "rl:"

# KEYS[1] = 限流 key
# ARGV[1] = 当前时间戳（秒）
# ARGV[2] = 窗口起点（秒）
# ARGV[3] = 上限
# ARGV[4] = 本次请求的唯一 member
# ARGV[5] = 过期毫秒
# 返回 {是否放行, 当前计数}
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local ttl_ms = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)
if count >= limit then
  return {0, count}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, ttl_ms)
return {1, count + 1}
"""


async def hit(key: str, limit: int, window: int) -> tuple[bool, int]:
    """记一次访问并判断是否超限，返回 (是否放行, 当前窗口内计数)。"""
    now = time.time()
    member = str(time.time_ns())
    try:
        result = await redis_client.eval(
            _SLIDING_WINDOW_LUA,
            1,
            f"{RATE_PREFIX}{key}",
            now,
            now - window,
            limit,
            member,
            (window + 1) * 1000,
        )
        return bool(result[0]), int(result[1])
    except Exception as exc:
        logger.warning("限流检查失败，本次放行（%s）：%s", key, exc)
        return True, 0


def client_ip(request: Request) -> str:
    """取客户端 IP。

    ⚠️ 直接读 `request.client.host`，落在 nginx 之类的反向代理后面拿到的是代理地址，
    所有用户会共享同一个限流桶。部署时要么改成解析 X-Forwarded-For（且只信任自己的
    代理），要么改用 uvicorn 的 `--proxy-headers`。
    """
    return request.client.host if request.client else "unknown"


async def enforce(key: str, limit: int, window: int, message: str) -> None:
    """限流入口：超限直接抛 429。路由里 `await enforce(...)` 一行搞定。"""
    allowed, _ = await hit(key, limit, window)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
