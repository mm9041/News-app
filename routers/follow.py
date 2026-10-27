"""关注：关注作者 / 分类，关注流。"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import follow as follow_crud
from models.news import News
from models.users import User
from schemas.base import NewsItemBase
from schemas.follow import FollowRequest
from utils.auth import get_current_user
from utils.response import success_response

router = APIRouter(prefix="/api/follow", tags=["follow"])


@router.post("")
async def add_follow(
        data: FollowRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    if data.target_type == "user" and data.target_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能关注自己")

    from crud import follow as follow_crud
    created = await follow_crud.add_follow(db, user.id, data.target_type, data.target_id)
    return success_response(
        data={"following": created},
        message="已关注" if created else "已经在关注列表里",
    )


@router.delete("")
async def remove_follow(
        data: FollowRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    from crud import follow as follow_crud
    removed = await follow_crud.remove_follow(db, user.id, data.target_type, data.target_id)
    return success_response(data={"following": not removed}, message="已取消关注" if removed else "本来就没关注")


@router.get("/status")
async def follow_status(
        target_type: Literal["user", "category", "source"] = Query(..., alias="targetType"),
        target_id: int = Query(..., ge=1, alias="targetId"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    from crud import follow as follow_crud
    following = await follow_crud.is_following(db, user.id, target_type, target_id)
    return success_response(data={"following": following}, message="获取关注状态成功")


@router.get("/authors")
async def list_followed_authors(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """我关注的作者，带各自的评论数。"""
    authors = await follow_crud.list_follows(db, user.id, "user")
    return success_response(data=authors, message="获取关注的作者成功")


@router.get("/feed")
async def follow_feed(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=50, alias="pageSize"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """关注流：关注的作者发的新闻 + 关注的分类下的新闻。"""
    skip = (page - 1) * page_size
    rows, total = await follow_crud.feed(db, user.id, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]
    return success_response(
        data={"list": items, "total": total, "hasMore": total > skip + len(items)},
        message="获取关注流成功",
    )


@router.get("/sources")
async def list_followed_sources(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """我关注的报纸，各带新闻数。"""
    from crud import follow as follow_crud

    sources = await follow_crud.list_followed_sources(db, user.id)
    return success_response(data=sources, message="获取关注的报纸成功")
