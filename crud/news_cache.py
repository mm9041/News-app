from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from cache import view_counter
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


async def get_news_detail(db: AsyncSession, news_id: int):
    stmt = select(News).where(News.id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


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
