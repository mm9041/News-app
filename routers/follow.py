"""关注作者：关注/取关/状态/关注列表 + 作者的新闻列表。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import follow as follow_crud
from models.users import User
from schemas.base import NewsItemBase
from schemas.common import ApiResponse
from schemas.follow import FollowAuthorNewsResponse, FollowedAuthorItem, FollowStatusResponse
from utils.api_docs import AUTHENTICATED_ERRORS, PUBLIC_READ_ERRORS
from utils.auth import get_current_user
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/follow", tags=["follow"])


@router.post("", response_model=ApiResponse[FollowStatusResponse], responses=AUTHENTICATED_ERRORS)
async def add_follow(
    name: str = Query(..., min_length=1, max_length=50, description="作者名"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    created = await follow_crud.add_follow(db, user.id, name)
    return success_response(
        data=FollowStatusResponse(following=created),
        message="已关注" if created else "已经在关注列表里",
    )


@router.delete("", response_model=ApiResponse[FollowStatusResponse], responses=AUTHENTICATED_ERRORS)
async def remove_follow(
    name: str = Query(..., min_length=1, max_length=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    removed = await follow_crud.remove_follow(db, user.id, name)
    return success_response(
        data=FollowStatusResponse(following=not removed),
        message="已取消关注" if removed else "本来就没关注",
    )


@router.get("/status", response_model=ApiResponse[FollowStatusResponse], responses=AUTHENTICATED_ERRORS)
async def follow_status(
    name: str = Query(..., min_length=1, max_length=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    following = await follow_crud.is_following(db, user.id, name)
    return success_response(data=FollowStatusResponse(following=following), message="获取关注状态成功")


@router.get("/authors", response_model=ApiResponse[list[FollowedAuthorItem]], responses=AUTHENTICATED_ERRORS)
async def list_followed_authors(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """我关注的作者，各带新闻数。"""
    authors = await follow_crud.list_followed_authors(db, user.id)
    return success_response(data=authors, message="获取关注的作者成功")


@router.get("/news", response_model=ApiResponse[FollowAuthorNewsResponse], responses=PUBLIC_READ_ERRORS)
async def list_news_by_author(
    name: str = Query(..., min_length=1, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    db: AsyncSession = Depends(get_database),
):
    """某个作者（报纸/人名）发布的全部新闻。"""
    skip = (page - 1) * page_size
    rows, total = await follow_crud.list_news_by_author(db, name, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]

    return success_response(
        data=FollowAuthorNewsResponse(
            list=items,
            total=total,
            has_more=calc_has_more(total, skip, len(items)),
            author=name.strip(),
        ),
        message="获取作者新闻成功",
    )
