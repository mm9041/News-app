from collections.abc import Iterable
from typing import Any

from config.cache_conf import get_json_cache, redis_client, set_cache
from utils.logger import get_logger

logger = get_logger(__name__)

CATEGORIES_KEY = "news:categories"
NEWS_LIST_PREFIX = "news_list:"
# 详情缓存的 key 前缀。放在 cache 层是为了让 crud/news_views 也能用，
# 而不必反向 import crud/news_cache（那会形成循环依赖）。
DETAIL_CACHE_PREFIX = "news:detail:"


async def get_cached_categories():
    return await get_json_cache(CATEGORIES_KEY)


# 设置缓存分类、配置：7200  列表：600  详情：1800  验证码：120
async def set_cache_categories(data: list[dict[str, Any]], expire: int = 7200):
    return await set_cache(CATEGORIES_KEY, data, expire)


async def set_cache_news_list(
    category_id: int | None, page: int, size: int, news_list: list[dict[str, Any]], expire: int = 1800
):
    category_part = category_id if category_id is not None else "all"
    key = f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"
    return await set_cache(key, news_list, expire)


async def get_cached_news_list(category_id: int | None, page: int, size: int):
    category_part = category_id if category_id is not None else "all"
    key = f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"
    return await get_json_cache(key)


async def delete_cache_pattern(pattern: str, batch_size: int = 500) -> int:
    """按模式批量删除缓存，返回删除的 key 数量。

    用 `SCAN` 而不是 `KEYS`：KEYS 是 O(N) 且会**阻塞 Redis 单线程**，
    key 一多（列表缓存按「分类:页码:页长」铺开）整个实例都会卡住。
    `cache/view_counter.snapshot_deltas` 出于同样的理由也用 SCAN。
    每攒够一批就 DEL 一次，避免一个 DEL 带几千个 key。
    """
    deleted = 0
    try:
        batch: list[str] = []
        async for key in redis_client.scan_iter(match=pattern, count=200):
            batch.append(key)
            if len(batch) >= batch_size:
                deleted += await redis_client.delete(*batch)
                batch.clear()
        if batch:
            deleted += await redis_client.delete(*batch)
        return deleted
    except Exception as e:
        # 缓存删不掉不该让业务失败 —— 最坏情况就是多显示一会儿旧数据
        logger.warning("删除缓存失败（%s）：%s", pattern, e)
        return deleted


async def invalidate_news_list(category_id: int | None) -> int:
    """某个分类的新闻列表发生变化时，清掉它全部分页的缓存。

    为什么必须主动失效：列表缓存是「读时回填」，而 `views` 会随着每次浏览详情变化。
    详情接口直接查库（所以是对的），列表接口却拿着 30 分钟前的快照 ——
    不主动清就会出现「详情页阅读量变了、首页不变」的怪现象。
    """
    category_part = category_id if category_id is not None else "all"
    return await delete_cache_pattern(f"{NEWS_LIST_PREFIX}{category_part}:*")


async def delete_detail_caches(news_ids: Iterable[int]) -> int:
    """批量删详情缓存，返回删除的 key 数。

    阅读量回写之后必须调用。详情缓存里存的是**写缓存那一刻的 views 快照**，
    对外展示的阅读量 = 快照 + 未回写增量。增量一旦被回写清零，展示值就会
    退回快照，表现为阅读量「倒退」（实测 7485 → 7484）。
    删掉让下一次请求回源拿最新值，代价是每条被刷新的新闻多一次查库。
    """
    ids = list(dict.fromkeys(news_ids))
    if not ids:
        return 0
    try:
        keys = [f"{DETAIL_CACHE_PREFIX}{news_id}" for news_id in ids]
        return await redis_client.delete(*keys)
    except Exception as e:
        # 缓存删不掉不该让回写失败：最坏只是多显示一会儿旧值，等 TTL 过期
        logger.warning("删除详情缓存失败（%d 条）：%s", len(ids), e)
        return 0
