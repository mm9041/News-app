"""管理后台接口。

整个 router 挂 `get_current_admin`：既保证每个接口都鉴权，
也不用在每个函数签名里重复写一遍依赖。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import admin_news
from schemas.admin import AdminNewsItemResponse, AdminNewsListResponse, AdminNewsUpsertRequest
from utils.auth import get_current_admin
from utils.response import success_response

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)


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
    return success_response(data=AdminNewsItemResponse.model_validate(news), message="获取新闻成功")


@router.post("/news")
async def create_news(data: AdminNewsUpsertRequest, db: AsyncSession = Depends(get_database)):
    news = await admin_news.create_news(db, data)
    return success_response(data=AdminNewsItemResponse.model_validate(news), message="创建成功")


@router.put("/news/{news_id}")
async def update_news(news_id: int, data: AdminNewsUpsertRequest, db: AsyncSession = Depends(get_database)):
    news = await admin_news.get_news(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    news = await admin_news.update_news(db, news, data)
    return success_response(data=AdminNewsItemResponse.model_validate(news), message="更新成功")


@router.delete("/news/{news_id}")
async def delete_news(news_id: int, db: AsyncSession = Depends(get_database)):
    news = await admin_news.get_news(db, news_id)
    if not news:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    await admin_news.delete_news(db, news)
    return success_response(message="删除成功")
