"""新闻评论。

设计取舍：
- 单层评论，不做楼中楼（回复需要树形渲染，先把主链跑通）
- 不做软删除：删了就是删了，新闻/用户被删时外键 CASCADE 一起清
- 列表公开可读；发布与删除需要登录；删除权限 = 本人 or 管理员
"""

from typing import Optional

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
    CommentUser,
)
from utils.auth import get_current_user, get_optional_user
from utils.response import success_response

router = APIRouter(prefix="/api/comment", tags=["comment"])


@router.get("/list")
async def list_comments(
        news_id: int = Query(..., alias="newsId", ge=1),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=50, alias="pageSize"),
        db: AsyncSession = Depends(get_database),
        current_user: Optional[User] = Depends(get_optional_user),
):
    """按时间倒序分页。游客也能看，登录后额外返回 canDelete。"""
    skip = (page - 1) * page_size
    rows, total = await comment_crud.list_comments(db, news_id, skip, page_size)

    items = [
        CommentItemResponse(
            id=item.id,
            content=item.content,
            created_at=item.created_at,
            user=CommentUser.model_validate(author),
            can_delete=bool(
                current_user
                and (current_user.id == item.user_id or current_user.is_admin)
            ),
        )
        for item, author in rows
    ]

    data = CommentListResponse(
        list=items,
        total=total,
        has_more=total > skip + len(items),
    )
    return success_response(data=data, message="获取评论成功")


@router.post("/add")
async def add_comment(
        data: CommentAddRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    # 先确认新闻存在，否则外键会直接抛 IntegrityError，变成一条看不懂的 400
    news = await news_cache.get_news_detail(db, data.news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    content = data.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="评论内容不能为空",
        )

    comment = await comment_crud.add_comment(db, data.news_id, user.id, content)

    # 通知新闻发布者。`news.user_id` 为空（历史种子数据）或自己评论自己的，都不发
    if news.user_id and news.user_id != user.id:
        await notification_crud.create(
            db,
            user_id=news.user_id,
            actor_id=user.id,
            type_="comment",
            news_id=data.news_id,
            comment_id=comment.id,
        )

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
