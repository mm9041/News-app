"""新闻评论（两级：评论 + 回复）。

权限与通知规则：
- 列表公开可读，登录后每项带 canDelete（本人或管理员）
- 发布需登录；回复别人的评论时通知被回复者，发一级评论时通知新闻发布者
- 删除权限 = 本人 or 管理员；删一级评论会级联删掉它的回复
- 不做软删除：删了就是删了，新闻/用户被删时外键 CASCADE 一起清
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import comment as comment_crud
from crud import news_cache
from crud import notification as notification_crud
from models.users import User
from schemas.comment import (
    CommentAddRequest,
    CommentItemResponse,
    CommentListResponse,
    CommentReply,
    CommentUser,
)
from utils.auth import get_current_user, get_optional_user
from utils.logger import get_logger
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/comment", tags=["comment"])
logger = get_logger(__name__)


def _can_delete(current_user: User | None, owner_id: int) -> bool:
    """本人或管理员。规则只写这一处，列表和详情不会不一致。"""
    return bool(current_user and (current_user.id == owner_id or current_user.is_admin))


@router.get("")
async def list_comments(
    news_id: int = Query(..., alias="newsId", ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    db: AsyncSession = Depends(get_database),
    current_user: User | None = Depends(get_optional_user),
):
    """一级评论分页，每条带出它下面的全部回复。"""
    skip = (page - 1) * page_size
    roots, replies_map, total = await comment_crud.list_comments(db, news_id, skip, page_size)

    items = []
    for comment, author in roots:
        replies = [
            CommentReply(
                id=reply.id,
                content=reply.content,
                created_at=reply.created_at,
                user=CommentUser.model_validate(reply_author),
                can_delete=_can_delete(current_user, reply.user_id),
                parent_id=reply.parent_id,
                reply_to=reply_to_name,
            )
            for reply, reply_author, reply_to_name in replies_map.get(comment.id, [])
        ]
        items.append(
            CommentItemResponse(
                id=comment.id,
                content=comment.content,
                created_at=comment.created_at,
                user=CommentUser.model_validate(author),
                can_delete=_can_delete(current_user, comment.user_id),
                parent_id=None,
                replies=replies,
            )
        )

    data = CommentListResponse(
        list=items,
        total=total,
        has_more=calc_has_more(total, skip, len(items)),
    )
    return success_response(data=data, message="获取评论成功")


@router.post("")
async def add_comment(
    data: CommentAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    news = await news_cache.get_news_detail(db, data.news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    content = data.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="评论内容不能为空",
        )

    # 回复：把 parent 归到所属的一级评论，同时记下「回复给谁」
    root_id: int | None = None
    reply_to_user_id: int | None = None
    if data.parent_id:
        parent = await comment_crud.get_comment(db, data.parent_id)
        if not parent or parent.news_id != data.news_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="被回复的评论不存在")
        root_id = parent.parent_id or parent.id
        reply_to_user_id = parent.user_id

    comment = await comment_crud.add_comment(db, data.news_id, user.id, content, root_id, reply_to_user_id)

    # 通知是附属动作：失败只记日志，不能返回 500 —— 此时评论已落库，
    # 用户看到「评论失败」重试会发出重复评论。
    try:
        if reply_to_user_id and reply_to_user_id != user.id:
            await notification_crud.create(
                db,
                user_id=reply_to_user_id,
                actor_id=user.id,
                type_="reply",
                news_id=data.news_id,
                comment_id=comment.id,
            )
        elif news.user_id and news.user_id != user.id:
            await notification_crud.create(
                db,
                user_id=news.user_id,
                actor_id=user.id,
                type_="comment",
                news_id=data.news_id,
                comment_id=comment.id,
            )
    except Exception as e:
        logger.warning("创建评论通知失败（comment_id=%s）：%s", comment.id, e)

    return success_response(data={"id": comment.id}, message="评论成功")


@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    comment = await comment_crud.get_comment(db, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")

    if comment.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能删除自己的评论")

    await comment_crud.delete_comment(db, comment)
    return success_response(message="删除成功")
