"""管理后台的新闻读写。

写操作之后必须让列表缓存失效：列表缓存 TTL 是 30 分钟，不清的话
后台改完新闻、前台要等半小时才看得到。
（阅读量走的是另一套 Redis 增量，不受这里影响。）
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.news_cache import invalidate_news_list
from models.news import News
from schemas.admin import AdminNewsUpsertRequest


async def list_news(db: AsyncSession, keyword: str | None, skip: int, limit: int):
    stmt = select(News)
    count_stmt = select(func.count(News.id))

    if keyword and keyword.strip():
        kw = keyword.strip()
        # 管理端搜索只匹配标题和作者：正文太长，模糊匹配既慢又没意义
        condition = or_(
            News.title.contains(kw, autoescape=True),
            News.author.contains(kw, autoescape=True),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(News.publish_time.desc(), News.id.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return rows, total


async def get_news(db: AsyncSession, news_id: int) -> News | None:
    result = await db.execute(select(News).where(News.id == news_id))
    return result.scalar_one_or_none()


async def create_news(db: AsyncSession, data: AdminNewsUpsertRequest) -> News:
    values = data.model_dump(exclude={"publish_time"})
    news = News(**values)
    # 不传发布时间就交给模型的 default（datetime.now）
    if data.publish_time:
        news.publish_time = data.publish_time

    db.add(news)
    await db.commit()
    await db.refresh(news)
    await invalidate_news_list(news.category_id)
    return news


async def update_news(db: AsyncSession, news: News, data: AdminNewsUpsertRequest) -> News:
    """PUT 语义：整份覆盖，传 null 就是清空该字段。"""
    old_category_id = news.category_id

    news.title = data.title
    news.description = data.description
    news.content = data.content
    news.image = data.image
    news.author = data.author
    news.category_id = data.category_id
    if data.publish_time:
        news.publish_time = data.publish_time

    await db.commit()
    await db.refresh(news)

    # 换了分类的话，旧分类的列表缓存也要清
    await invalidate_news_list(old_category_id)
    if news.category_id != old_category_id:
        await invalidate_news_list(news.category_id)
    return news


async def delete_news(db: AsyncSession, news: News) -> None:
    category_id = news.category_id
    await db.delete(news)
    await db.commit()
    await invalidate_news_list(category_id)
