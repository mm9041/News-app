"""基于 Redis 的固定窗口限流。

只用在「会被暴力尝试」或「会烧钱」的接口上：登录、注册、AI 对话。
不引第三方库 —— 固定窗口用 `INCR` + `EXPIRE` 两条命令就够，且能复用现有的 Redis。

Redis 不可用时一律放行：限流是保护措施，不能因为它自己挂了就把业务拦死。
代价是 Redis 故障期间失去这层防护，属于可接受的取舍。
"""

import time

from fastapi import HTTPException, Request, status

from config.cache_conf import redis_client
from utils.logger import get_logger

logger = get_logger(__name__)

RATE_PREFIX = "rl:"


async def hit(key: str, limit: int, window: int) -> tuple[bool, int]:
    """记一次访问并判断是否超限，返回 (是否放行, 本窗口内已计次数)。"""
    bucket = int(time.time()) // window
    redis_key = f"{RATE_PREFIX}{key}:{bucket}"
    try:
        count = await redis_client.incr(redis_key)
        if count == 1:
            # 只在第一次计数时设过期，避免每次请求都刷新 TTL
            await redis_client.expire(redis_key, window + 1)
        return count <= limit, count
    except Exception as e:
        logger.warning("限流检查失败，本次放行（%s）：%s", key, e)
        return True, 0


def client_ip(request: Request) -> str:
    """取客户端 IP。

    ⚠️ 直接读 `request.client.host`，落在 nginx 之类的反向代理后面拿到的是代理地址，
    所有用户会共享同一个限流桶。部署时要么改成解析 X-Forwarded-For（且只信任自己的
    代理），要么改用 uvicorn 的 `--proxy-headers`。
    """
    return request.client.host if request.client else "unknown"


async def enforce(key: str, limit: int, window: int, message: str) -> None:
    allowed, _ = await hit(key, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
        )
