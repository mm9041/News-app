"""站内通知的读写。"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import NewsComment
from models.news import News
from models.notification import Notification
from models.users import User


async def create(
    db: AsyncSession,
    user_id: int,
    actor_id: int,
    type_: str,
    news_id: int,
    comment_id: int | None = None,
) -> Notification | None:
    """给 user_id 发一条通知。自己操作自己的内容时不发（调用方保证）。"""
    notification = Notification(
        user_id=user_id,
        actor_id=actor_id,
        type=type_,
        news_id=news_id,
        comment_id=comment_id,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def list_for_user(db: AsyncSession, user_id: int, skip: int, limit: int):
    """返回 ([(通知, 触发者, 新闻标题, 评论内容)], 总数)。"""
    total = (await db.execute(select(func.count(Notification.id)).where(Notification.user_id == user_id))).scalar_one()

    if not total:
        return [], 0

    stmt = (
        select(Notification, User, News.title, NewsComment.content)
        .join(User, User.id == Notification.actor_id)
        .join(News, News.id == Notification.news_id)
        .outerjoin(NewsComment, NewsComment.id == Notification.comment_id)
        .where(Notification.user_id == user_id)
        # created_at 是秒精度，同一秒内多条通知靠 id 定序
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1], row[2], row[3]) for row in rows], total


async def count_unread(db: AsyncSession, user_id: int) -> int:
    return (
        await db.execute(
            select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
    ).scalar_one()


async def mark_read(db: AsyncSession, user_id: int, notification_id: int) -> bool:
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount
