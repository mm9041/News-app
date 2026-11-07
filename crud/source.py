"""报纸来源的数据访问。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.news import News
from models.source import Source


async def get_source(db: AsyncSession, source_id: int) -> Source | None:
    result = await db.execute(select(Source).where(Source.id == source_id))
    return result.scalar_one_or_none()


async def list_news_by_source(db: AsyncSession, source_id: int, skip: int, limit: int):
    """某份报纸下的全部新闻，按发布时间倒序。"""
    total = (await db.execute(select(func.count(News.id)).where(News.source_id == source_id))).scalar_one()

    if not total:
        return [], 0

    stmt = (
        select(News)
        .where(News.source_id == source_id)
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all()), total
