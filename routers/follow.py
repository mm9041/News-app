"""关注作者：关注/取关/状态/关注列表 + 作者的新闻列表。"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import follow as follow_crud
from models.users import User
from schemas.base import NewsItemBase
from utils.auth import get_current_user
from utils.response import success_response

router = APIRouter(prefix="/api/follow", tags=["follow"])


@router.post("")
async def add_follow(
        name: str = Query(..., min_length=1, max_length=50, description="作者名"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    created = await follow_crud.add_follow(db, user.id, name)
    return success_response(
        data={"following": created},
        message="已关注" if created else "已经在关注列表里",
    )


@router.delete("")
async def remove_follow(
        name: str = Query(..., min_length=1, max_length=50),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    removed = await follow_crud.remove_follow(db, user.id, name)
    return success_response(
        data={"following": not removed},
        message="已取消关注" if removed else "本来就没关注",
    )


@router.get("/status")
async def follow_status(
        name: str = Query(..., min_length=1, max_length=50),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    following = await follow_crud.is_following(db, user.id, name)
    return success_response(data={"following": following}, message="获取关注状态成功")


@router.get("/authors")
async def list_followed_authors(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """我关注的作者，各带新闻数。"""
    authors = await follow_crud.list_followed_authors(db, user.id)
    return success_response(data=authors, message="获取关注的作者成功")


@router.get("/news")
async def list_news_by_author(
        name: str = Query(..., min_length=1, max_length=50),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=50, alias="pageSize"),
        db: AsyncSession = Depends(get_database),
):
    """某个作者（报纸/人名）发布的全部新闻。"""
    skip = (page - 1) * page_size
    rows, total = await follow_crud.list_news_by_author(db, name, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]

    return success_response(
        data={
            "list": items,
            "total": total,
            "hasMore": total > skip + len(items),
            "author": name.strip(),
        },
        message="获取作者新闻成功",
    )
