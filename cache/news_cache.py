from typing import List, Dict, Any, Optional

from config.cache_conf import get_json_cache, set_cache, redis_client
from utils.logger import get_logger

logger = get_logger(__name__)

CATEGORIES_KEY = "news:categories"
NEWS_LIST_PREFIX = "news_list:"


async def get_cached_categories():
    return await get_json_cache(CATEGORIES_KEY)


# 设置缓存分类、配置：7200  列表：600  详情：1800  验证码：120
async def set_cache_categories(data: List[Dict[str, Any]], expire: int = 7200):
    return await set_cache(CATEGORIES_KEY, data, expire)


async def set_cache_news_list(category_id: Optional[int], page: int, size: int, news_list: List[Dict[str, Any]],
                              expire: int = 1800):
    category_part = category_id if category_id is not None else "all"
    key = f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"
    return await set_cache(key, news_list, expire)


async def get_cached_news_list(category_id: Optional[int], page: int, size: int):
    category_part = category_id if category_id is not None else "all"
    key = f"{NEWS_LIST_PREFIX}{category_part}:{page}:{size}"
    return await get_json_cache(key)


async def delete_cache_pattern(pattern: str) -> int:
    """按模式批量删除缓存，返回删除的 key 数量。"""
    try:
        keys = await redis_client.keys(pattern)
        if not keys:
            return 0
        return await redis_client.delete(*keys)
    except Exception as e:
        # 缓存删不掉不该让业务失败 —— 最坏情况就是多显示一会儿旧数据
        logger.warning("删除缓存失败（%s）：%s", pattern, e)
        return 0


async def invalidate_news_list(category_id: Optional[int]) -> int:
    """某个分类的新闻列表发生变化时，清掉它全部分页的缓存。

    为什么必须主动失效：列表缓存是「读时回填」，而 `views` 会随着每次浏览详情变化。
    详情接口直接查库（所以是对的），列表接口却拿着 30 分钟前的快照 ——
    不主动清就会出现「详情页阅读量变了、首页不变」的怪现象。
    """
    category_part = category_id if category_id is not None else "all"
    return await delete_cache_pattern(f"{NEWS_LIST_PREFIX}{category_part}:*")
