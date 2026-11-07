"""标签接口。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import tag as tag_crud
from schemas.base import NewsItemBase
from schemas.common import ApiResponse
from schemas.tag import TagBrief, TagHotItem, TagNewsResponse
from utils.api_docs import PUBLIC_READ_ERRORS
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/tag", tags=["tag"])


@router.get("/hot", response_model=ApiResponse[list[TagHotItem]], responses=PUBLIC_READ_ERRORS)
async def list_hot_tags(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_database),
):
    """标签墙：按被引用次数排序。"""
    rows = await tag_crud.hot_tags(db, limit)
    data = [{"id": tag_id, "name": name, "count": count} for tag_id, name, count in rows]
    return success_response(data=data, message="获取标签成功")


@router.get("/{tag_id}/news", response_model=ApiResponse[TagNewsResponse], responses=PUBLIC_READ_ERRORS)
async def list_news_by_tag(
    tag_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    db: AsyncSession = Depends(get_database),
):
    tag = await tag_crud.get_tag(db, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")

    skip = (page - 1) * page_size
    rows, total = await tag_crud.list_by_tag(db, tag_id, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]

    return success_response(
        data=TagNewsResponse(
            list=items,
            total=total,
            has_more=calc_has_more(total, skip, len(items)),
            tag=TagBrief(id=tag.id, name=tag.name),
        ),
        message="获取标签新闻成功",
    )
