from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio
import random
from datetime import datetime

from cache import view_counter
from config.cache_conf import get_json_cache, redis_client, set_cache
from cache.news_cache import (
    get_cached_categories,
    set_cache_categories,
    get_cached_news_list,
    set_cache_news_list,
    invalidate_news_list,
)
from crud.news_views import apply_view_deltas
from models.news import Category, News
from schemas.base import NewsItemBase
from utils.logger import get_logger

logger = get_logger(__name__)

DETAIL_CACHE_PREFIX = "news:detail:"
DETAIL_LOCK_PREFIX = "lock:news:detail:"
DETAIL_TTL_BASE = 120
DETAIL_TTL_JITTER = 60      # 抖动范围，避免同批 key 同时过期（雪崩）
NULL_TTL = 30               # 空值缓存，防穿透
LOCK_TTL = 3
LOCK_WAIT_ROUNDS = 10
LOCK_WAIT_INTERVAL = 0.05


async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100):
    cached_categories = await get_cached_categories()
    if cached_categories:
        return cached_categories
    stmt = select(Category).offset(skip).limit(limit)
    result = await db.execute(stmt)
    categories = result.scalars().all()
    if categories:
        categories = jsonable_encoder(categories)
        await set_cache_categories(categories, expire=7200)
    return categories


async def get_news_list(db: AsyncSession, category_id: int, skip: int = 0, limit: int = 100) -> list[NewsItemBase]:
    """分页取某个分类的新闻列表。

    两条路径（缓存命中 / 回源查库）都返回同一个 NewsItemBase 列表。
    之前命中缓存时用 `News(**cache_item)` 重建 ORM 对象，而缓存里存的是
    NewsItemBase 的字段（不含 content），于是「冷缓存多返回 content、热缓存不返回」，
    响应体随缓存状态漂移。统一成 schema 后契约稳定，输出也统一成 camelCase，
    前端 NewsItem 里用的 publishTime 才对得上。
    """
    page = skip // limit + 1
    cached_list = await get_cached_news_list(category_id, page, limit)
    if cached_list:
        # 缓存里存的是库里的原值，这里再叠加尚未回写的阅读量增量
        return await apply_view_deltas([NewsItemBase.model_validate(item) for item in cached_list])

    stmt = (select(News)
            .where(News.category_id == category_id)
            # 不显式排序时，分页顺序取决于存储引擎/执行计划，翻页可能重复或漏条；
            # id 做次级键是为了 publish_time 相同（同一天批量导入）时顺序仍然稳定。
            .order_by(News.publish_time.desc(), News.id.desc())
            .offset(skip).limit(limit))
    result = await db.execute(stmt)
    items = [NewsItemBase.model_validate(row) for row in result.scalars().all()]
    if items:
        await set_cache_news_list(
            category_id, page, limit,
            [item.model_dump(mode="json", by_alias=False) for item in items],
        )
    return await apply_view_deltas(items)


async def get_news_count(db: AsyncSession, category_id: int):
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    result = await db.execute(stmt)
    return result.scalar_one()


def _dump_news(news: News) -> dict:
    return {
        "id": news.id,
        "title": news.title,
        "description": news.description,
        "content": news.content,
        "image": news.image,
        "author": news.author,
        "category_id": news.category_id,
        "user_id": news.user_id,
        "source_id": news.source_id,
        "views": news.views,
        "publish_time": news.publish_time.isoformat() if news.publish_time else None,
        "created_at": news.created_at.isoformat() if news.created_at else None,
        "updated_at": news.updated_at.isoformat() if news.updated_at else None,
    }


def _load_news(payload: dict) -> News:
    data = dict(payload)
    for field in ("publish_time", "created_at", "updated_at"):
        value = data.get(field)
        if isinstance(value, str):
            data[field] = datetime.fromisoformat(value)
    return News(**data)


async def get_news_detail(db: AsyncSession, news_id: int):
    """新闻详情（带缓存）。

    缓存三件套都在这一个函数里：
    - 穿透：查不到的 id 也写一个 30 秒的空标记，避免反复打库
    - 击穿：缓存过期的瞬间只放一个请求回源，其余等它写回（Redis 互斥锁）
    - 雪崩：TTL = 基础值 + 随机抖动，同批 key 不会同时失效

    ⚠️ 缓存里的 views 是快照，比库里的真实值旧。这里可以接受：
    阅读量展示走「库内值 + Redis 增量」，而 Redis 一旦不可用，缓存本身也读不到，
    所以不会出现拿旧值覆盖库的情况。
    """
    key = f"{DETAIL_CACHE_PREFIX}{news_id}"

    cached = await get_json_cache(key)
    if cached is not None:
        if cached.get("__null__"):
            return None
        try:
            return _load_news(cached)
        except Exception:
            # 结构变了（比如新增了列）就当未命中，别让旧缓存把请求打挂
            logger.warning("详情缓存解析失败，回源：news_id=%s", news_id)

    lock_key = f"{DETAIL_LOCK_PREFIX}{news_id}"
    locked = False
    try:
        locked = bool(await redis_client.set(lock_key, "1", nx=True, ex=LOCK_TTL))
    except Exception:
        locked = False

    if not locked:
        # 别人正在回源，短暂等待并重试缓存
        for _ in range(LOCK_WAIT_ROUNDS):
            await asyncio.sleep(LOCK_WAIT_INTERVAL)
            cached = await get_json_cache(key)
            if cached is not None:
                return None if cached.get("__null__") else _load_news(cached)
        # 等不到就自己查：宁可多一次查询，也不能让请求卡死

    try:
        result = await db.execute(select(News).where(News.id == news_id))
        news = result.scalar_one_or_none()

        if news is None:
            await set_cache(key, {"__null__": True}, NULL_TTL)
            return None

        await set_cache(key, _dump_news(news), DETAIL_TTL_BASE + random.randint(0, DETAIL_TTL_JITTER))
        return news
    finally:
        if locked:
            try:
                await redis_client.delete(lock_key)
            except Exception:
                pass


async def invalidate_news_detail(news_id: int) -> None:
    """后台改/删新闻后调用，否则详情最多 3 分钟仍是旧的。"""
    try:
        await redis_client.delete(f"{DETAIL_CACHE_PREFIX}{news_id}")
    except Exception as e:
        logger.warning("清理详情缓存失败（news_id=%s）：%s", news_id, e)


async def increase_news_views(db: AsyncSession, news_id: int, current_views: int) -> int:
    """浏览 +1，返回本次请求应当展示的阅读量。

    正常路径只动 Redis（`INCR`），不产生 UPDATE、也不清列表缓存；
    增量由后台任务定时批量写回数据库。Redis 不可用时退回直写数据库：
    缓存层可以挂，阅读量不能停。

    `current_views` 传查询时读到的库内值，返回 `库内值 + 未回写增量`。
    不能把自增后的值写回 ORM 对象再读，那样在并发下会彼此覆盖。
    """
    delta = await view_counter.increase(news_id)
    if delta is not None:
        return current_views + delta

    stmt = update(News).where(News.id == news_id).values(views=News.views + 1)
    await db.execute(stmt)
    await db.commit()
    return current_views + 1


async def get_related_news(db: AsyncSession, news_id: int, category_id: int, limit: int = 5):
    stmt = select(News).where(
        News.category_id == category_id,
        News.id != news_id,
    ).order_by(
        News.views.desc(),
        News.publish_time.desc()
    ).limit(limit)
    result = await db.execute(stmt)
    related_news = result.scalars().all()
    rows = [{
        "id": news.id,
        "title": news.title,
        "content": news.content,
        "image": news.image,
        "author": news.author,
        "publishTime": news.publish_time,
        "categoryId": news.category_id,
        "views": news.views
    } for news in related_news]

    # 相关推荐是直接查库的，要比对一下还没回写的阅读量增量，否则会比列表页小
    deltas = await view_counter.get_deltas([row["id"] for row in rows])
    for row in rows:
        delta = deltas.get(row["id"])
        if delta:
            row["views"] += delta
    return rows
