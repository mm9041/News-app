"""后台统计。

都是聚合查询，数据量小，直接查库不做缓存 —— 后台看板不需要实时到秒，
但也不值得为它引入一套缓存失效逻辑。
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import NewsComment
from models.news import Category, News
from models.users import User


async def overview(db: AsyncSession) -> dict:
    news_count = (await db.execute(select(func.count(News.id)))).scalar_one()
    comment_count = (await db.execute(select(func.count(NewsComment.id)))).scalar_one()
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_views = (await db.execute(select(func.coalesce(func.sum(News.views), 0)))).scalar_one()

    return {
        "news": news_count,
        "comments": comment_count,
        "users": user_count,
        "views": int(total_views or 0),
    }


async def trend(db: AsyncSession, days: int) -> list[dict]:
    """近 N 天的新增新闻 / 评论数，缺失的日期补 0。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    since = today - timedelta(days=days - 1)

    news_rows = await db.execute(
        select(func.date(News.created_at), func.count(News.id))
        .where(News.created_at >= since)
        .group_by(func.date(News.created_at))
    )
    comment_rows = await db.execute(
        select(func.date(NewsComment.created_at), func.count(NewsComment.id))
        .where(NewsComment.created_at >= since)
        .group_by(func.date(NewsComment.created_at))
    )

    news_map = {str(day): count for day, count in news_rows.all()}
    comment_map = {str(day): count for day, count in comment_rows.all()}

    result = []
    for offset in range(days):
        day = since + timedelta(days=offset)
        key = day.strftime("%Y-%m-%d")
        result.append({
            "date": key,
            "news": news_map.get(key, 0),
            "comments": comment_map.get(key, 0),
        })
    return result


async def categories(db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        select(
            Category.name,
            func.count(News.id),
            func.coalesce(func.sum(News.views), 0),
        )
        .join(News, News.category_id == Category.id, isouter=True)
        .group_by(Category.id, Category.name)
        .order_by(func.count(News.id).desc())
    )
    return [
        {"name": name, "news": count, "views": int(views or 0)}
        for name, count, views in rows.all()
    ]


async def top_news(db: AsyncSession, limit: int) -> list[dict]:
    rows = await db.execute(
        select(News.id, News.title, News.views, News.category_id)
        .order_by(News.views.desc(), News.id.desc())
        .limit(limit)
    )
    return [
        {"id": news_id, "title": title, "views": views, "categoryId": category_id}
        for news_id, title, views, category_id in rows.all()
    ]
