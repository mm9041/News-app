from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import news_cache

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


@router.get("/detail")
async def get_news_detail(news_id: int = Query(default=..., alias="id"), db: AsyncSession = Depends(get_database)):
    news_detail = await news_cache.get_news_detail(db, news_id)
    if not news_detail:
        raise HTTPException(status_code=404, detail="新闻不存在")

    # 阅读量 +1：正常只写 Redis 计数器，由后台任务批量回写数据库。
    # 这里不再 db.refresh，也不再清该分类的列表缓存 —— 列表缓存里存的是库内原值，
    # 读的时候会叠加未回写的增量，所以两者天然一致，缓存不该被一次浏览打穿。
    views = await news_cache.increase_news_views(db, news_detail.id, news_detail.views)

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
            "relatedNews": related_news
        }
    }
