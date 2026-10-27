"""评论的数据访问。

列表用 join 一次把作者带出来，避免逐条查用户（N+1）。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import NewsComment
from models.users import User


async def list_comments(db: AsyncSession, news_id: int, skip: int, limit: int):
    """返回 ([(评论, 作者), ...], 总数)。"""
    total = (
        await db.execute(
            select(func.count(NewsComment.id)).where(NewsComment.news_id == news_id)
        )
    ).scalar_one()

    if not total:
        return [], 0

    stmt = (
        select(NewsComment, User)
        .join(User, User.id == NewsComment.user_id)
        .where(NewsComment.news_id == news_id)
        # id 做次级键：created_at 是秒精度，同一秒内的多条评论顺序会不定
        .order_by(NewsComment.created_at.desc(), NewsComment.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows], total


async def add_comment(db: AsyncSession, news_id: int, user_id: int, content: str) -> NewsComment:
    comment = NewsComment(news_id=news_id, user_id=user_id, content=content)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comment(db: AsyncSession, comment_id: int) -> NewsComment | None:
    result = await db.execute(select(NewsComment).where(NewsComment.id == comment_id))
    return result.scalar_one_or_none()


async def delete_comment(db: AsyncSession, comment: NewsComment) -> None:
    await db.delete(comment)
    await db.commit()
