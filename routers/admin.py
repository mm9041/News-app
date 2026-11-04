"""管理后台接口。

整个 router 挂 `get_current_admin`：既保证每个接口都鉴权，
也不用在每个函数签名里重复写一遍依赖。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import update

from config.db_conf import get_database
from crud import admin_news, stats
from crud import tag as tag_crud
from crud import users as users_crud
from models.users import User
from schemas.admin import (
    AdminFlagRequest,
    AdminNewsItemResponse,
    AdminNewsListResponse,
    AdminNewsUpsertRequest,
    AdminUserItemResponse,
    AdminUserListResponse,
    BanRequest,
)
from utils.auth import get_current_admin
from utils.response import success_response

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)


async def _with_tags(db: AsyncSession, news) -> AdminNewsItemResponse:
    """详情/创建/更新的响应带上标签；列表不带（省一次 N+1）。"""
    data = AdminNewsItemResponse.model_validate(news)
    tags = await tag_crud.list_news_tags(db, news.id)
    data.tags = [tag.name for tag in tags]
    return data


@router.get("/news")
async def list_news(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
        keyword: Optional[str] = Query(None, max_length=50),
        db: AsyncSession = Depends(get_database),
):
    skip = (page - 1) * page_size
    rows, total = await admin_news.list_news(db, keyword, skip, page_size)
    data = AdminNewsListResponse(
        list=[AdminNewsItemResponse.model_validate(row) for row in rows],
        total=total,
        has_more=total > skip + len(rows),
    )
    return success_response(data=data, message="获取新闻列表成功")


@router.get("/news/{news_id}")
async def get_news(news_id: int, db: AsyncSession = Depends(get_database)):
    news = await admin_news.get_news(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")
    return success_response(data=await _with_tags(db, news), message="获取新闻成功")


@router.post("/news")
async def create_news(
        data: AdminNewsUpsertRequest,
        user: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_database),
):
    news = await admin_news.create_news(db, data, user.id)
    return success_response(data=await _with_tags(db, news), message="创建成功")


@router.put("/news/{news_id}")
async def update_news(news_id: int, data: AdminNewsUpsertRequest, db: AsyncSession = Depends(get_database)):
    news = await admin_news.get_news(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    news = await admin_news.update_news(db, news, data)
    return success_response(data=await _with_tags(db, news), message="更新成功")


@router.delete("/news/{news_id}")
async def delete_news(news_id: int, db: AsyncSession = Depends(get_database)):
    news = await admin_news.get_news(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    await admin_news.delete_news(db, news)
    return success_response(message="删除成功")


@router.get("/stats")
async def get_stats(
        days: int = Query(7, ge=1, le=30, description="趋势天数"),
        top: int = Query(10, ge=1, le=20, description="热门新闻条数"),
        db: AsyncSession = Depends(get_database),
):
    """看板数据一次性返回，避免前端发四个请求。"""
    return success_response(
        data={
            "overview": await stats.overview(db),
            "trend": await stats.trend(db, days),
            "categories": await stats.categories(db),
            "topNews": await stats.top_news(db, top),
        },
        message="获取统计数据成功",
    )


# ---------------------------- 用户管理 ----------------------------


@router.get("/users")
async def list_users(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=50, alias="pageSize"),
        keyword: Optional[str] = Query(None, max_length=50),
        db: AsyncSession = Depends(get_database),
):
    skip = (page - 1) * page_size
    rows, total = await users_crud.list_users_for_admin(db, keyword, skip, page_size)

    items = [
        AdminUserItemResponse(
            id=user.id,
            username=user.username,
            nickname=user.nickname,
            avatar=user.avatar,
            gender=user.gender,
            bio=user.bio,
            phone=user.phone,
            is_admin=user.is_admin,
            banned=bool(user.status),
            comment_count=count,
            created_at=user.created_at,
        )
        for user, count in rows
    ]
    data = AdminUserListResponse(list=items, total=total)
    return success_response(data=data, message="获取用户列表成功")


@router.put("/users/{user_id}/ban")
async def ban_user(
        user_id: int,
        data: BanRequest,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_database),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用自己")

    result = await db.execute(
        update(User).where(User.id == user_id).values(status=1 if data.banned else 0)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return success_response(message="已禁用" if data.banned else "已解禁")


@router.put("/users/{user_id}/admin")
async def set_user_admin(
        user_id: int,
        data: AdminFlagRequest,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_database),
):
    if user_id == admin.id and not data.is_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能取消自己的管理员权限")

    result = await db.execute(
        update(User).where(User.id == user_id).values(is_admin=data.is_admin)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return success_response(message="已设为管理员" if data.is_admin else "已取消管理员")


@router.delete("/users/{user_id}")
async def delete_user(
        user_id: int,
        admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_database),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 级联清掉 token/评论/点赞/收藏/历史/通知；news.user_id 会置 NULL（新闻保留）
    await db.delete(user)
    await db.commit()
    return success_response(message="删除成功")
