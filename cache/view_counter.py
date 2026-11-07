"""阅读量计数器：把「浏览 +1」先记在 Redis，再由后台定时批量回写数据库。

为什么要这么做：

原来详情页每被打开一次就 `UPDATE news SET views = views + 1`，紧接着清空该分类
**全部**列表缓存。新闻 App 的主路径就是「列表 → 点进详情」，于是列表缓存刚写好就被
下一次浏览清掉，30 分钟的 TTL 从未真正生效，缓存等于没有；同时每条新闻都产生一次
UPDATE 行锁。

现在的分工：
- 写：`INCR view:delta:{id}`，只动 Redis，不碰数据库。
- 读：数据库里的值 + Redis 里尚未回写的增量 = 当前真实阅读量。
      列表缓存里存的是**数据库原值**，每次读取时再叠加增量 ——
      不能把叠加后的值写进缓存，否则下次命中会重复累加。
- 刷：后台每 N 秒把增量批量写回数据库，成功后 `DECRBY` 掉已回写的部分
      （用 DECRBY 而不是 DEL：刷库期间新来的 +1 不会被误删）。

Redis 不可用时全部退化为直写数据库，行为与改造前一致 —— 缓存层本来就该是可选的。
"""

from collections.abc import Iterable

from config.cache_conf import redis_client
from utils.logger import get_logger

logger = get_logger(__name__)

VIEW_DELTA_PREFIX = "view:delta:"


def _key(news_id: int) -> str:
    return f"{VIEW_DELTA_PREFIX}{news_id}"


async def increase(news_id: int) -> int | None:
    """给某条新闻的待回写增量 +1，返回累计增量；Redis 不可用返回 None。"""
    try:
        return await redis_client.incr(_key(news_id))
    except Exception as e:
        logger.warning("阅读量计数失败（news_id=%s）：%s", news_id, e)
        return None


async def get_deltas(news_ids: Iterable[int]) -> dict[int, int]:
    """批量取出多条新闻的待回写增量。用 MGET 一次拿完，避免 N 次往返。"""
    ids = list(dict.fromkeys(news_ids))  # 去重且保持顺序
    if not ids:
        return {}
    try:
        values = await redis_client.mget([_key(i) for i in ids])
    except Exception as e:
        logger.warning("读取阅读量增量失败：%s", e)
        return {}
    return {i: int(v) for i, v in zip(ids, values) if v and int(v) > 0}


async def snapshot_deltas(limit: int = 500) -> dict[int, int]:
    """扫描出最多 limit 条待回写的增量，供后台回写使用。

    用 SCAN 而不是 KEYS：KEYS 是 O(N) 且会阻塞 Redis 单线程，生产环境禁用。
    """
    keys: list[str] = []
    try:
        async for key in redis_client.scan_iter(f"{VIEW_DELTA_PREFIX}*", count=200):
            keys.append(key)
            if len(keys) >= limit:
                break
        if not keys:
            return {}
        values = await redis_client.mget(keys)
    except Exception as e:
        logger.warning("扫描阅读量增量失败：%s", e)
        return {}

    result: dict[int, int] = {}
    for key, value in zip(keys, values):
        if not value:
            continue
        try:
            news_id = int(key.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
        delta = int(value)
        if delta > 0:
            result[news_id] = delta
    return result


async def commit(news_id: int, delta: int) -> None:
    """回写成功后扣掉已回写的增量；减到 0 就把 key 删掉，避免 scan 扫到一堆空 key。

    这里刻意不用 DEL：从「读出 delta」到「写库成功」之间可能又有新的 INCR 进来，
    直接 DEL 会把那部分增量一起丢掉。DECRBY 只减掉已经落库的那一份。
    """
    try:
        remaining = await redis_client.decrby(_key(news_id), delta)
        if remaining <= 0:
            await redis_client.delete(_key(news_id))
    except Exception as e:
        logger.warning("扣减阅读量增量失败（news_id=%s）：%s", news_id, e)


async def close() -> None:
    """应用退出时释放 Redis 连接池。"""
    try:
        await redis_client.aclose()
    except Exception as e:
        logger.warning("关闭 Redis 连接失败：%s", e)
