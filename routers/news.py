from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import like as like_crud
from crud import news_cache, news_search
from crud import recommend as recommend_crud
from models.users import User
from schemas.base import NewsItemBase
from utils.auth import get_current_user, get_optional_user

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/categories")
async def get_categories(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=200),
        db: AsyncSession = Depends(get_database)
):
    categories = await news_cache.get_categories(db, skip, limit)
    return {
        "code": 200,
        "message": "获取分类成功",
        "data": categories
    }


@router.get("/list")
async def get_news_list(
        category_id: int = Query(default=..., alias="categoryId", ge=1),
        # page/pageSize 必须限死范围：pageSize=0 会在 crud 里触发 skip // limit 除零，
        # page=0 会算出负 offset 让 MySQL 直接报语法错 —— 两者都会变成 500。
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=10, alias="pageSize", ge=1, le=100),
        db: AsyncSession = Depends(get_database)
):
    offset = (page - 1) * page_size
    news_list = await news_cache.get_news_list(db, category_id, offset, page_size)
    total = await news_cache.get_news_count(db, category_id)
    has_more = total > offset + len(news_list)
    return {
        "code": 200,
        "message": "获取新闻列表成功",
        "data": {
            "list": news_list,
            "total": total,
            "hasMore": has_more
        }
    }


@router.get("/search")
async def search_news(
        keyword: str = Query(..., min_length=1, max_length=50),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
        db: AsyncSession = Depends(get_database)
):
    """按关键词搜索标题/摘要/正文。

    返回结构与列表接口一致（同样不含 content），前端可以复用列表组件。
    """
    skip = (page - 1) * page_size
    rows, total = await news_search.search_news(db, keyword, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]
    has_more = total > skip + len(items)
    return {
        "code": 200,
        "message": "搜索成功",
        "data": {
            "list": items,
            "total": total,
            "hasMore": has_more,
            "keyword": keyword.strip(),
        }
    }


@router.get("/detail")
async def get_news_detail(
        news_id: int = Query(default=..., alias="id"),
        db: AsyncSession = Depends(get_database),
        current_user: Optional[User] = Depends(get_optional_user),
):
    news_detail = await news_cache.get_news_detail(db, news_id)
    if not news_detail:
        raise HTTPException(status_code=404, detail="新闻不存在")

    # 阅读量 +1：正常只写 Redis 计数器，由后台任务批量回写数据库。
    # 这里不再 db.refresh，也不再清该分类的列表缓存 —— 列表缓存里存的是库内原值，
    # 读的时候会叠加未回写的增量，所以两者天然一致，缓存不该被一次浏览打穿。
    views = await news_cache.increase_news_views(db, news_detail.id, news_detail.views)

    # 点赞是实时 COUNT（走 idx_news_like_news），不缓存、不冗余计数
    likes = await like_crud.count_likes(db, news_id)
    is_liked = False
    if current_user:
        is_liked = await like_crud.is_liked(db, news_id, current_user.id)

    related_news = await news_cache.get_related_news(db, news_detail.id, news_detail.category_id)
    return {
        "code": 200,
        "message": "获取新闻详情成功",
        "data": {
            "id": news_detail.id,
            "title": news_detail.title,
            "content": news_detail.content,
            "image": news_detail.image,
            "author": news_detail.author,
            "publishTime": news_detail.publish_time,
            "categoryId": news_detail.category_id,
            "views": views,
            "likes": likes,
            "isLiked": is_liked,
            "relatedNews": related_news
        }
    }


@router.get("/recommend")
async def get_recommend(
        limit: int = Query(8, ge=1, le=20),
        db: AsyncSession = Depends(get_database),
        current_user: Optional[User] = Depends(get_optional_user),
):
    """猜你喜欢：按收藏/浏览的分类偏好推荐；游客退化为全站热门。"""
    rows = await recommend_crud.recommend_news(
        db, current_user.id if current_user else None, limit
    )
    items = [NewsItemBase.model_validate(row) for row in rows]
    return {"code": 200, "message": "获取推荐成功", "data": {"list": items}}


@router.put("/{news_id}/like")
async def like_news(
        news_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """点赞。重复调用返回同样结果（INSERT IGNORE，幂等）。"""
    news = await news_cache.get_news_detail(db, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")

    await like_crud.like(db, news_id, user.id)
    likes = await like_crud.count_likes(db, news_id)
    return {"code": 200, "message": "已点赞", "data": {"liked": True, "likes": likes}}


@router.delete("/{news_id}/like")
async def unlike_news(
        news_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """取消点赞。没点过也返回成功（DELETE 0 行，幂等）。"""
    await like_crud.unlike(db, news_id, user.id)
    likes = await like_crud.count_likes(db, news_id)
    return {"code": 200, "message": "已取消点赞", "data": {"liked": False, "likes": likes}}
