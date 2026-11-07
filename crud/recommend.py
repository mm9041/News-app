"""个性化推荐。

不引模型，用行为数据做一个可解释的排序：

1. 统计分类偏好 —— 收藏权重 3、浏览权重 1（收藏是主动行为，信号更强）
2. 取权重最高的 3 个分类，按发布时间取**未读过**的新闻
3. 不足时用全站热门（views 降序）补齐
4. 游客、或没有任何行为的新用户 → 直接给热门

只排除浏览历史、不排除已收藏：收藏过的新闻通常还值得再看，
而「刚看完又推给我」才是明显的坏体验。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.favorite import Favorite
from models.history import History
from models.news import News

FAVORITE_WEIGHT = 3
HISTORY_WEIGHT = 1
TOP_CATEGORIES = 3


async def _hot_news(
    db: AsyncSession,
    limit: int,
    exclude: set[int] | None = None,
    exclude_read_by: int | None = None,
):
    stmt = select(News)
    if exclude:
        stmt = stmt.where(News.id.not_in(exclude))
    if exclude_read_by:
        # 热门补齐也要排掉已读，否则「刚看完的又出现在猜你喜欢里」
        stmt = stmt.where(News.id.not_in(select(History.news_id).where(History.user_id == exclude_read_by)))
    stmt = stmt.order_by(News.views.desc(), News.publish_time.desc(), News.id.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def _category_weights(db: AsyncSession, user_id: int) -> dict[int, int]:
    weights: dict[int, int] = {}

    rows = await db.execute(
        select(News.category_id, func.count().label("cnt"))
        .join(Favorite, Favorite.news_id == News.id)
        .where(Favorite.user_id == user_id)
        .group_by(News.category_id)
    )
    for category_id, count in rows:
        weights[category_id] = weights.get(category_id, 0) + count * FAVORITE_WEIGHT

    rows = await db.execute(
        select(News.category_id, func.count().label("cnt"))
        .join(History, History.news_id == News.id)
        .where(History.user_id == user_id)
        .group_by(News.category_id)
    )
    for category_id, count in rows:
        weights[category_id] = weights.get(category_id, 0) + count * HISTORY_WEIGHT

    return weights


async def recommend_news(db: AsyncSession, user_id: int | None, limit: int = 8):
    """返回推荐新闻列表（ORM 对象）。"""
    if not user_id:
        return await _hot_news(db, limit)

    weights = await _category_weights(db, user_id)
    if not weights:
        return await _hot_news(db, limit)

    top_categories = sorted(weights, key=weights.get, reverse=True)[:TOP_CATEGORIES]
    read_ids = select(History.news_id).where(History.user_id == user_id)

    stmt = (
        select(News)
        .where(News.category_id.in_(top_categories), News.id.not_in(read_ids))
        .order_by(News.publish_time.desc(), News.id.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if len(rows) >= limit:
        return rows

    # 兴趣分类里的未读新闻不够，用热门补齐（同样排除已读）
    picked = {item.id for item in rows}
    rows.extend(await _hot_news(db, limit - len(rows), exclude=picked, exclude_read_by=user_id))
    return rows
