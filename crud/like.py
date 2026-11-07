"""新闻点赞。

点赞用 `INSERT IGNORE`，取消用 `DELETE`，两者都是幂等的：
前端重复点、弱网重试都不会把计数算错（这也是没用 toggle 的原因）。
"""

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.like import NewsLike


async def count_likes(db: AsyncSession, news_id: int) -> int:
    return (await db.execute(select(func.count(NewsLike.id)).where(NewsLike.news_id == news_id))).scalar_one()


async def is_liked(db: AsyncSession, news_id: int, user_id: int) -> bool:
    result = await db.execute(select(NewsLike.id).where(NewsLike.news_id == news_id, NewsLike.user_id == user_id))
    return result.scalar_one_or_none() is not None


async def like(db: AsyncSession, news_id: int, user_id: int) -> bool:
    """点赞。返回 True 表示这次是新增，False 表示之前已经赞过。"""
    stmt = (
        insert(NewsLike).values(news_id=news_id, user_id=user_id).prefix_with("IGNORE")  # 命中唯一索引时静默跳过
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


async def unlike(db: AsyncSession, news_id: int, user_id: int) -> bool:
    """取消点赞。返回 True 表示确实删掉了一条。"""
    result = await db.execute(delete(NewsLike).where(NewsLike.news_id == news_id, NewsLike.user_id == user_id))
    await db.commit()
    return result.rowcount > 0
