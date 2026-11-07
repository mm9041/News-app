"""后台统计。

都是聚合查询，数据量小，直接查库不做缓存 —— 后台看板不需要实时到秒，
但也不值得为它引入一套缓存失效逻辑。

为了压掉往返次数：overview 的四个 COUNT/SUM 合成一条 SQL，trend 的
新闻/评论两条 UNION ALL 合成一条。不在这里用 asyncio.gather ——
AsyncSession 不允许同一会话并发执行（会报 concurrent operations）。
"""

from datetime import datetime, timedelta

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import NewsComment
from models.news import Category, News
from models.users import User


async def overview(db: AsyncSession) -> dict:
    # 四个标量子查询合成一条 SQL，一次往返拿全看板数字
    news_count = select(func.count(News.id)).scalar_subquery()
    comment_count = select(func.count(NewsComment.id)).scalar_subquery()
    user_count = select(func.count(User.id)).scalar_subquery()
    total_views = select(func.coalesce(func.sum(News.views), 0)).scalar_subquery()

    row = (await db.execute(select(news_count, comment_count, user_count, total_views))).one()
    return {
        "news": row[0],
        "comments": row[1],
        "users": row[2],
        "views": int(row[3] or 0),
    }


async def trend(db: AsyncSession, days: int) -> list[dict]:
    """近 N 天的新增新闻 / 评论数，缺失的日期补 0。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    since = today - timedelta(days=days - 1)

    news_day = func.date(News.created_at)
    comment_day = func.date(NewsComment.created_at)

    # 两张表按日期聚合，UNION ALL 合并成一次往返
    stmt = union_all(
        select(
            literal("news").label("kind"),
            news_day.label("day"),
            func.count(News.id).label("cnt"),
        )
        .where(News.created_at >= since)
        .group_by(news_day),
        select(
            literal("comment").label("kind"),
            comment_day.label("day"),
            func.count(NewsComment.id).label("cnt"),
        )
        .where(NewsComment.created_at >= since)
        .group_by(comment_day),
    )

    news_map: dict[str, int] = {}
    comment_map: dict[str, int] = {}
    for kind, day, count in (await db.execute(stmt)).all():
        (news_map if kind == "news" else comment_map)[str(day)] = count

    result = []
    for offset in range(days):
        day = since + timedelta(days=offset)
        key = day.strftime("%Y-%m-%d")
        result.append(
            {
                "date": key,
                "news": news_map.get(key, 0),
                "comments": comment_map.get(key, 0),
            }
        )
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
    return [{"name": name, "news": count, "views": int(views or 0)} for name, count, views in rows.all()]


async def top_news(db: AsyncSession, limit: int) -> list[dict]:
    rows = await db.execute(
        select(News.id, News.title, News.views, News.category_id)
        .order_by(News.views.desc(), News.id.desc())
        .limit(limit)
    )
    return [
        {"id": news_id, "title": title, "views": views, "category_id": category_id}
        for news_id, title, views, category_id in rows.all()
    ]
