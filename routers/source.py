"""报纸来源接口。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import source as source_crud
from schemas.base import NewsItemBase
from utils.auth import get_optional_user
from utils.response import success_response

router = APIRouter(prefix="/api/source", tags=["source"])


@router.get("/{source_id}/news")
async def list_news_by_source(
        source_id: int,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
        db: AsyncSession = Depends(get_database),
        # 登录与否不影响列表，NewsItemBase 需要的公开字段都来自 News 本身
        _user=Depends(get_optional_user),
):
    source = await source_crud.get_source(db, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报纸不存在")

    skip = (page - 1) * page_size
    rows, total = await source_crud.list_news_by_source(db, source_id, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]

    return success_response(
        data={
            "list": items,
            "total": total,
            "hasMore": total > skip + len(items),
            "source": {"id": source.id, "name": source.name},
        },
        message="获取报纸新闻成功",
    )
