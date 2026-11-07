from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import like as like_crud
from crud import news_cache, news_search
from crud import notification as notification_crud
from crud import recommend as recommend_crud
from models.like import NewsLike
from models.news import News
from models.tag import Tag
from models.users import User
from schemas.base import NewsItemBase
from schemas.common import ApiResponse
from schemas.news import (
    CategoryItem,
    NewsDetailResponse,
    NewsLikeResponse,
    NewsListResponse,
    NewsRecommendResponse,
    NewsSearchResponse,
    SuggestNewsItem,
    SuggestResponse,
    TagItem,
)
from utils.api_docs import PUBLIC_READ_ERRORS, documented_errors
from utils.auth import get_current_user, get_optional_user
from utils.logger import get_logger
from utils.pagination import MAX_PAGE_SIZE, calc_has_more
from utils.response import success_response

router = APIRouter(prefix="/api/news", tags=["news"])
logger = get_logger(__name__)
NEWS_ERRORS = documented_errors(404, 422)
LIKE_ERRORS = documented_errors(401, 403, 404, 422)


@router.get("/categories", response_model=ApiResponse[list[CategoryItem]], responses=PUBLIC_READ_ERRORS)
async def get_categories(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), db: AsyncSession = Depends(get_database)
):
    categories = await news_cache.get_categories(db, skip, limit)
    return success_response(data=categories, message="获取分类成功")


@router.get("", response_model=ApiResponse[NewsListResponse], responses=NEWS_ERRORS)
async def get_news_list(
    category_id: int = Query(default=..., alias="categoryId", ge=1),
    # page/pageSize 必须限死范围：pageSize=0 会在 crud 里触发 skip // limit 除零，
    # page=0 会算出负 offset 让 MySQL 直接报语法错 —— 两者都会变成 500。
    page: int = Query(default=1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    db: AsyncSession = Depends(get_database),
):
    offset = (page - 1) * page_size
    news_list = await news_cache.get_news_list(db, category_id, offset, page_size)
    total = await news_cache.get_news_count(db, category_id)
    data = NewsListResponse.model_validate(
        {
            "list": news_list,
            "total": total,
            "has_more": calc_has_more(total, offset, len(news_list)),
        }
    )
    return success_response(data=data, message="获取新闻列表成功")


@router.get("/search", response_model=ApiResponse[NewsSearchResponse], responses=NEWS_ERRORS)
async def search_news(
    keyword: str = Query(..., min_length=1, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize"),
    db: AsyncSession = Depends(get_database),
):
    """按关键词搜索标题/摘要/正文。

    返回结构与列表接口一致（同样不含 content），前端可以复用列表组件。
    """
    skip = (page - 1) * page_size
    rows, total = await news_search.search_news(db, keyword, skip, page_size)
    items = [NewsItemBase.model_validate(row) for row in rows]
    data = NewsSearchResponse.model_validate(
        {
            "list": items,
            "total": total,
            "has_more": calc_has_more(total, skip, len(items)),
            "keyword": keyword.strip(),
        }
    )
    return success_response(data=data, message="搜索成功")


@router.get("/recommend", response_model=ApiResponse[NewsRecommendResponse], responses=NEWS_ERRORS)
async def get_recommend(
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_database),
    current_user: User | None = Depends(get_optional_user),
):
    """猜你喜欢：按收藏/浏览的分类偏好推荐；游客退化为全站热门。"""
    rows = await recommend_crud.recommend_news(db, current_user.id if current_user else None, limit)
    items = [NewsItemBase.model_validate(row) for row in rows]
    return success_response(data={"list": items}, message="获取推荐成功")


@router.put("/{news_id}/like", response_model=ApiResponse[NewsLikeResponse], responses=LIKE_ERRORS)
async def like_news(
    news_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """点赞。重复调用返回同样结果（INSERT IGNORE，幂等）。"""
    news = await news_cache.get_news_detail(db, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="新闻不存在")

    created = await like_crud.like(db, news_id, user.id)
    likes = await like_crud.count_likes(db, news_id)

    # 只在「本次真的新增了点赞」时通知，重复点赞不会反复骚扰发布者。
    # 通知是附属动作：失败只记日志，点赞已落库，不该因此返回 500。
    if created and news.user_id and news.user_id != user.id:
        try:
            await notification_crud.create(
                db,
                user_id=news.user_id,
                actor_id=user.id,
                type_="like",
                news_id=news_id,
            )
        except Exception as e:
            logger.warning("创建点赞通知失败（news_id=%s）：%s", news_id, e)

    return success_response(data={"liked": True, "likes": likes}, message="已点赞")


@router.delete("/{news_id}/like", response_model=ApiResponse[NewsLikeResponse], responses=LIKE_ERRORS)
async def unlike_news(
    news_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    """取消点赞。没点过也返回成功（DELETE 0 行，幂等）。"""
    await like_crud.unlike(db, news_id, user.id)
    likes = await like_crud.count_likes(db, news_id)
    return success_response(data={"liked": False, "likes": likes}, message="已取消点赞")


@router.get("/suggest", response_model=ApiResponse[SuggestResponse], responses=NEWS_ERRORS)
async def suggest(
    keyword: str = Query(..., min_length=1, max_length=20),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_database),
):
    """输入联想：标题包含关键词的新闻 + 名称匹配的标签。"""
    kw = keyword.strip()
    if not kw:
        return success_response(data=SuggestResponse(news=[], tags=[]))

    news_rows = await db.execute(
        select(News.id, News.title)
        .where(News.title.contains(kw, autoescape=True))
        .order_by(News.views.desc(), News.id.desc())
        .limit(limit)
    )
    tag_rows = await db.execute(select(Tag.id, Tag.name).where(Tag.name.contains(kw, autoescape=True)).limit(5))

    return success_response(
        data=SuggestResponse(
            news=[SuggestNewsItem(id=row[0], title=row[1]) for row in news_rows.all()],
            tags=[TagItem(id=row[0], name=row[1]) for row in tag_rows.all()],
        )
    )


# 注意：放在所有静态 GET 路径（/categories、/search、/recommend、/suggest）之后，
# 否则 /{news_id} 会先把它们吞掉（int 转换失败变成 422）。
@router.get("/{news_id}", response_model=ApiResponse[NewsDetailResponse], responses=NEWS_ERRORS)
async def get_news_detail(
    news_id: int,
    db: AsyncSession = Depends(get_database),
    current_user: User | None = Depends(get_optional_user),
):
    news_detail = await news_cache.get_news_detail(db, news_id)
    if not news_detail:
        raise HTTPException(status_code=404, detail="新闻不存在")

    # 阅读量 +1：正常只写 Redis 计数器，由后台任务批量回写数据库。
    # 这里不再 db.refresh，也不再清该分类的列表缓存 —— 列表缓存里存的是库内原值，
    # 读的时候会叠加未回写的增量，所以两者天然一致，缓存不该被一次浏览打穿。
    views = await news_cache.increase_news_views(db, news_detail.id, news_detail.views)

    # 点赞统计 + 是否已赞合并成一条 SQL（原来是两次往返，压测显示这是主要延迟之一）
    if current_user:
        likes_stmt = select(
            func.count(NewsLike.id),
            func.coalesce(func.sum(case((NewsLike.user_id == current_user.id, 1), else_=0)), 0),
        ).where(NewsLike.news_id == news_id)
        like_count, liked_count = (await db.execute(likes_stmt)).one()
        likes = like_count or 0
        is_liked = bool(liked_count)
    else:
        likes = await like_crud.count_likes(db, news_id)
        is_liked = False

    # 标签 + 相关推荐走独立缓存：命中时只剩上面这一次「点赞」查库，
    # 而它们本身变动很慢，没必要每次详情都查库。
    extras = await news_cache.get_detail_extras(db, news_detail.id, news_detail.category_id)
    data = NewsDetailResponse.model_validate(
        {
            "id": news_detail.id,
            "title": news_detail.title,
            "content": news_detail.content,
            "image": news_detail.image,
            "author": news_detail.author,
            "publish_time": news_detail.publish_time,
            "category_id": news_detail.category_id,
            "author_id": news_detail.user_id,
            "source_id": news_detail.source_id,
            "views": views,
            "likes": likes,
            "is_liked": is_liked,
            "tags": extras["tags"],
            "related_news": extras["related"],
        }
    )
    return success_response(data=data, message="获取新闻详情成功")
