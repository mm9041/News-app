"""站内通知。

只覆盖「别人评论/点赞了我发布的新闻」这一种场景 —— 新闻的发布者记在
`news.user_id` 上（后台创建时写入），历史种子数据没有发布者，不会产生通知。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import notification as notification_crud
from models.users import User
from schemas.notification import (
    NotificationActor,
    NotificationItemResponse,
    NotificationListResponse,
)
from utils.auth import get_current_user
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/notification", tags=["notification"])


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    skip = (page - 1) * page_size
    rows, total = await notification_crud.list_for_user(db, user.id, skip, page_size)
    unread = await notification_crud.count_unread(db, user.id)

    items = [
        NotificationItemResponse(
            id=item.id,
            type=item.type,
            news_id=item.news_id,
            news_title=title or "",
            comment_preview=(content[:60] if content else None),
            is_read=item.is_read,
            created_at=item.created_at,
            actor=NotificationActor.model_validate(actor),
        )
        for item, actor, title, content in rows
    ]

    data = NotificationListResponse(
        list=items,
        total=total,
        unread=unread,
        has_more=calc_has_more(total, skip, len(items)),
    )
    return success_response(data=data, message="获取通知成功")


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    count = await notification_crud.count_unread(db, user.id)
    return success_response(data={"count": count}, message="获取未读数成功")


@router.put("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    updated = await notification_crud.mark_all_read(db, user.id)
    return success_response(data={"updated": updated}, message="已全部标记为已读")


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    # 条件里带 user_id，别人的通知不会被误标
    updated = await notification_crud.mark_read(db, user.id, notification_id)
    return success_response(data={"updated": 1 if updated else 0}, message="已标记为已读")
