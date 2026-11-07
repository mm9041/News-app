"""站内通知。

只覆盖「别人评论/点赞了我发布的新闻」这一种场景 —— 新闻的发布者记在
`news.user_id` 上（后台创建时写入），历史种子数据没有发布者，不会产生通知。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import notification as notification_crud
from models.users import User
from schemas.common import ApiResponse
from schemas.notification import (
    NotificationActor,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationReadRequest,
)
from utils.api_docs import AUTHENTICATED_ERRORS
from utils.auth import get_current_user
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/notification", tags=["notification"])


@router.get("", response_model=ApiResponse[NotificationListResponse], responses=AUTHENTICATED_ERRORS)
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


@router.get("/unread-count", response_model=ApiResponse[dict])
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    count = await notification_crud.count_unread(db, user.id)
    return success_response(data={"count": count}, message="获取未读数成功")


async def _mark_all_read(user: User, db: AsyncSession):
    updated = await notification_crud.mark_all_read(db, user.id)
    return success_response(data={"updated": updated}, message="已全部标记为已读")


@router.patch("", response_model=ApiResponse[dict], responses=AUTHENTICATED_ERRORS)
async def update_notifications(
    _data: NotificationReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """把当前用户的通知批量标记为已读。"""

    return await _mark_all_read(user, db)


@router.put("/read-all", include_in_schema=False, deprecated=True)
async def mark_all_read_legacy(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """兼容旧客户端的别名，新代码使用 PATCH /api/notification。"""

    return await _mark_all_read(user, db)


async def _mark_read(notification_id: int, user: User, db: AsyncSession):
    # 条件里带 user_id，别人的通知不会被误标
    updated = await notification_crud.mark_read(db, user.id, notification_id)
    return success_response(data={"updated": 1 if updated else 0}, message="已标记为已读")


@router.patch("/{notification_id}", response_model=ApiResponse[dict], responses=AUTHENTICATED_ERRORS)
async def update_notification(
    notification_id: int,
    _data: NotificationReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """更新单条通知的已读状态。"""

    return await _mark_read(notification_id, user, db)


@router.put("/{notification_id}/read", include_in_schema=False, deprecated=True)
async def mark_read_legacy(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """兼容旧客户端的别名，新代码使用 PATCH /api/notification/{id}。"""

    return await _mark_read(notification_id, user, db)
