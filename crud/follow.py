"""关注作者。

作者是字符串（可能是报纸名「海南日报」，也可能是人名「Dr. Chen」），
直接用 news.author 做关注对象：follow.target_type='author'，
target_name 存作者名，target_id 置 0（user/category 用这一列，本类型不用）。
"""

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.follow import Follow
from models.news import News

MAX_NAME_LEN = 50


def _clean(name: str | None) -> str:
    return (name or "").strip()[:MAX_NAME_LEN]


async def add_follow(db: AsyncSession, user_id: int, target_name: str) -> bool:
    """关注作者。返回 True 表示这次是新增，False 表示之前已关注（幂等）。"""
    name = _clean(target_name)
    if not name:
        return False

    result = await db.execute(
        insert(Follow)
        .values(user_id=user_id, target_type="author", target_id=0, target_name=name)
        .prefix_with("IGNORE")
    )
    await db.commit()
    return result.rowcount > 0


async def remove_follow(db: AsyncSession, user_id: int, target_name: str) -> bool:
    name = _clean(target_name)
    if not name:
        return False

    result = await db.execute(
        delete(Follow).where(
            Follow.user_id == user_id,
            Follow.target_type == "author",
            Follow.target_name == name,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def is_following(db: AsyncSession, user_id: int, target_name: str) -> bool:
    name = _clean(target_name)
    if not name:
        return False

    result = await db.execute(
        select(Follow.id).where(
            Follow.user_id == user_id,
            Follow.target_type == "author",
            Follow.target_name == name,
        )
    )
    return result.scalar_one_or_none() is not None


async def list_followed_authors(db: AsyncSession, user_id: int):
    """我关注的作者，各带新闻数。"""
    rows = await db.execute(
        select(Follow.target_name, func.count(News.id))
        .outerjoin(News, News.author == Follow.target_name)
        .where(Follow.user_id == user_id, Follow.target_type == "author")
        .group_by(Follow.target_name)
        .order_by(func.count(News.id).desc(), Follow.target_name.asc())
    )
    return [{"name": name, "newsCount": count} for name, count in rows.all()]


async def list_news_by_author(db: AsyncSession, author: str, skip: int, limit: int):
    """某个作者（报纸/人名）发布的全部新闻，按发布时间倒序。"""
    name = _clean(author)
    total = (
        await db.execute(select(func.count(News.id)).where(News.author == name))
    ).scalar_one()

    if not total:
        return [], 0

    stmt = (
        select(News)
        .where(News.author == name)
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all()), total
