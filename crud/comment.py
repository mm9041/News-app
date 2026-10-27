"""评论的数据访问。

两级结构：一级评论 + 它下面的回复。回复的 `parent_id` 始终指向一级评论，
「回复给谁」单独记在 `reply_to_user_id`，这样渲染时不会出现无限嵌套。
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from models.comment import NewsComment
from models.users import User


async def list_comments(db: AsyncSession, news_id: int, skip: int, limit: int):
    """返回 (一级评论, {一级评论ID: [(回复, 作者, 被回复人昵称)]}, 一级评论总数)。

    分页只针对一级评论；每条一级评论的回复一次性全部带出
    （单条新闻的评论量很小，不值得再为回复做一层分页）。
    """
    total = (
        await db.execute(
            select(func.count(NewsComment.id)).where(
                NewsComment.news_id == news_id, NewsComment.parent_id.is_(None)
            )
        )
    ).scalar_one()

    if not total:
        return [], {}, 0

    roots_stmt = (
        select(NewsComment, User)
        .join(User, User.id == NewsComment.user_id)
        .where(NewsComment.news_id == news_id, NewsComment.parent_id.is_(None))
        # created_at 是秒精度，同一秒内的多条靠 id 定序
        .order_by(NewsComment.created_at.desc(), NewsComment.id.desc())
        .offset(skip)
        .limit(limit)
    )
    roots = [(row[0], row[1]) for row in (await db.execute(roots_stmt)).all()]
    root_ids = [comment.id for comment, _ in roots]
    if not root_ids:
        return [], {}, total

    author = aliased(User)
    reply_to = aliased(User)
    replies_stmt = (
        select(NewsComment, author, reply_to.nickname, reply_to.username)
        .join(author, author.id == NewsComment.user_id)
        .outerjoin(reply_to, reply_to.id == NewsComment.reply_to_user_id)
        .where(NewsComment.parent_id.in_(root_ids))
        # 回复按时间正序，读起来像对话
        .order_by(NewsComment.created_at.asc(), NewsComment.id.asc())
    )

    replies_map: dict[int, list] = {}
    for comment, reply_author, rt_nickname, rt_username in (await db.execute(replies_stmt)).all():
        replies_map.setdefault(comment.parent_id, []).append(
            (comment, reply_author, rt_nickname or rt_username)
        )

    return roots, replies_map, total


async def add_comment(
        db: AsyncSession,
        news_id: int,
        user_id: int,
        content: str,
        parent_id: Optional[int] = None,
        reply_to_user_id: Optional[int] = None,
) -> NewsComment:
    comment = NewsComment(
        news_id=news_id,
        user_id=user_id,
        content=content,
        parent_id=parent_id,
        reply_to_user_id=reply_to_user_id,
    )
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
