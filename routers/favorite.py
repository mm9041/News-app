from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_404_NOT_FOUND

from config.db_conf import get_database
from crud import favorite
from crud.favorite import add_news_favorite, is_news_favorite, remove_news_favorite
from crud.news_cache import news_exists
from models.users import User
from schemas.favorite import (
    FavoriteAddRequest,
    FavoriteCheckResponse,
    FavoriteListResponse,
    FavoriteNewsItemResponse,
    FavoriteRemoveResponse,
)
from utils.auth import get_current_user
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/favorite", tags=["favorite"])


@router.get("/{news_id}")
async def check_favorite(
    news_id: int = Path(..., ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    is_favorite = await is_news_favorite(db, user.id, news_id)
    return success_response(message="检查收藏状态成功", data=FavoriteCheckResponse(is_favorite=is_favorite))


@router.post("")
async def add_favorite(
    data: FavoriteAddRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_database)
):
    # 先判存在：否则要等外键报错，变成 400「关联数据不存在」——语义应该是 404
    if not await news_exists(db, data.news_id):
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="新闻不存在")

    result = await add_news_favorite(db, user.id, data.news_id)
    return success_response(message="添加收藏成功", data=result)


@router.delete("/{news_id}")
async def remove_favorite(
    news_id: int = Path(..., ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """取消收藏。

    和点赞一样做成**幂等**：没收藏过也返回成功。
    弱网重试、或者两个标签页同时点，都不该弹出「收藏不存在」。
    """
    removed = await remove_news_favorite(db, user.id, news_id)
    return success_response(
        message="取消收藏成功" if removed else "本来就没有收藏",
        data=FavoriteRemoveResponse(removed=removed),
    )


@router.get("")
async def get_favorite_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    rows, total = await favorite.get_favorite_list(db, user.id, page, page_size)
    # 显式挑字段。原来用 `{**news.__dict__, ...}` 展开，会把 `_sa_instance_state`
    # 这类 ORM 内部状态一起塞进响应，只是碰巧被 Pydantic 当成私有属性忽略了。
    favorite_list = [
        FavoriteNewsItemResponse(
            id=news.id,
            title=news.title,
            description=news.description,
            image=news.image,
            author=news.author,
            category_id=news.category_id,
            views=news.views,
            publish_time=news.publish_time,
            favorite_id=favorite_id,
            favorite_time=favorite_time,
        )
        for news, favorite_time, favorite_id in rows
    ]
    has_more = calc_has_more(total, (page - 1) * page_size, len(favorite_list))
    return success_response(
        message="获取收藏列表成功",
        data=FavoriteListResponse(list=favorite_list, total=total, has_more=has_more),
    )


@router.delete("")
async def clear_favorite_route(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_database)):
    count = await favorite.remove_all_favorites(db, user.id)
    return success_response(message=f"清空了{count}条记录")
