import os
from pathlib import Path
from typing import Any

import json
import redis.asyncio as redis
from dotenv import load_dotenv
from redis.backoff import NoBackoff
from redis.retry import Retry

from utils.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# 缓存是「可选的加速层」，不是「必须可用的依赖」。
# 但 redis-py 8.x 默认带 3 次指数退避重试，且没有连接超时 —— 实测 Redis 一停，
# 单次 get 要等 26.9 秒才抛异常走降级分支，等于把整个站点拖死。
# 这里把连接/读超时压到 0.5s 并关掉重试：Redis 不可用时快速失败，立刻回源查库。
REDIS_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", "0.5"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.5"))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
    socket_timeout=REDIS_SOCKET_TIMEOUT,
    retry=Retry(NoBackoff(), 0),
)


async def get_json_cache(key: str):
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning("获取 JSON 缓存失败：%s", e)
        return None


async def set_cache(key: str, value: Any, expire: int = 3600):
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await redis_client.set(key, value, expire)
        return None
    except Exception as e:
        logger.warning("设置缓存失败：%s", e)
        return None
