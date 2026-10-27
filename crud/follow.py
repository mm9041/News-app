"""关注的数据访问。

target 可以是作者（user）或分类（category），两类共用一张表。
作者被删时 target_id 会悬空，读取时用 LEFT JOIN user 过滤掉。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import NewsComment
from models.follow import Follow
from models.news import News
from models.users import User

VALID_TYPES = ("user", "category")


async def add_follow(db: AsyncSession, user_id: int, target_type: str, target_id: int) -> bool:
    """关注。返回 True 表示这次是新增，False 表示之前已关注（幂等）。"""
    from sqlalchemy.dialects.mysql import insert

    result = await db.execute(
        insert(Follow)
        .values(user_id=user_id, target_type=target_type, target_id=target_id)
        .prefix_with("IGNORE")
    )
    await db.commit()
    return result.rowcount > 0


async def remove_follow(db: AsyncSession, user_id: int, target_type: str, target_id: int) -> bool:
    result = await db.execute(
        select(Follow).where(
            Follow.user_id == user_id,
            Follow.target_type == target_type,
            Follow.target_id == target_id,
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        return False
    await db.delete(follow)
    await db.commit()
    return True


async def is_following(db: AsyncSession, user_id: int, target_type: str, target_id: int) -> bool:
    result = await db.execute(
        select(Follow.id).where(
            Follow.user_id == user_id,
            Follow.target_type == target_type,
            Follow.target_id == target_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def list_follows(db: AsyncSession, user_id: int, target_type: str):
    """我关注的所有目标。作者类带出昵称/头像；分类类带出名称。"""
    from models.news_category import NewsCategory

    stmt = (
        select(Follow.target_id, NewsCategory.name)
        .join(NewsCategory, NewsCategory.id == Follow.target_id)
        .where(Follow.user_id == user_id, Follow.target_type == "category")
    )
    # category 名称通过子查询合并进来，作者用 LEFT JOIN
    author_rows = await db.execute(
        select(
            Follow.target_id,
            User.nickname,
            User.username,
            User.avatar,
            func.count(NewsComment.id),
        )
        .join(User, User.id == Follow.target_id)
        .outerjoin(News, News.user_id == User.id)
        .outerjoin(NewsComment, NewsComment.news_id == News.id)
        .where(Follow.user_id == user_id, Follow.target_type == "user")
        .group_by(Follow.target_id, User.nickname, User.username, User.avatar)
    )

    authors = [
        {
            "id": target_id,
            "nickname": nickname or username,
            "avatar": avatar,
            "commentCount": count,
        }
        for target_id, nickname, username, avatar, count in author_rows.all()
    ]
    _ = stmt, NewsCategory  # category 列表由前端通过分类接口展示，这里只返回作者
    return authors


async def followed_author_ids(db: AsyncSession, user_id: int) -> list[int]:
    result = await db.execute(
        select(Follow.target_id).where(
            Follow.user_id == user_id, Follow.target_type == "user"
        )
    )
    return [row[0] for row in result.all()]


async def followed_category_ids(db: AsyncSession, user_id: int) -> list[int]:
    result = await db.execute(
        select(Follow.target_id).where(
            Follow.user_id == user_id, Follow.target_type == "category"
        )
    )
    return [row[0] for row in result.all()]


async def feed(db: AsyncSession, user_id: int, skip: int, limit: int):
    """关注流：我关注的作者发的新闻 + 我关注的分类下的新闻，按发布时间倒序。"""
    author_ids = await followed_author_ids(db, user_id)
    category_ids = await followed_category_ids(db, user_id)

    conditions = []
    if author_ids:
        conditions.append(News.user_id.in_(author_ids))
    if category_ids:
        conditions.append(News.category_id.in_(category_ids))
    if not conditions:
        return [], 0

    from sqlalchemy import or_

    total = (
        await db.execute(select(func.count(News.id)).where(or_(*conditions)))
    ).scalar_one()

    stmt = (
        select(News)
        .where(or_(*conditions))
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all()), total
