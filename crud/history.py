from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import History
from models.news import News


async def add_history(db: AsyncSession, user_id: int, news_id: int):
    """记录一次浏览。

    用 `INSERT ... ON DUPLICATE KEY UPDATE` 而不是「先查后插」：
    后者在并发下会插出重复行（同一篇新闻在历史里出现多次），
    而且中间那段时间差没有任何约束兜底。
    这里依赖 history 表的 `user_news_unique (user_id, news_id)` 唯一索引。

    重复浏览只更新时间、id 不变，所以列表里仍然是同一条，只是排到最前。
    """
    now = datetime.now()
    stmt = (
        insert(History).values(user_id=user_id, news_id=news_id, view_time=now).on_duplicate_key_update(view_time=now)
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(select(History).where(History.user_id == user_id, History.news_id == news_id))
    return result.scalar_one_or_none()


async def get_history_list(db: AsyncSession, user_id: int, page: int = 1, page_size: int = 10):
    offset = (page - 1) * page_size
    count_query = select(func.count(History.id)).where(History.user_id == user_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    query = (
        select(News, History.view_time.label("view_time"), History.id.label("history_id"))
        .join(History, History.news_id == News.id)
        .where(History.user_id == user_id)
        # id 做次级键：view_time 是 TIMESTAMP 秒精度，同一秒内的多条记录
        # 只按时间排序顺序不确定，翻页会重复或漏条。索引 idx_user_view 也按这个顺序建。
        .order_by(History.view_time.desc(), History.id.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()
    return rows, total


async def delete_history(db: AsyncSession, user_id: int, news_id: int):
    """
    删除历史记录
    """
    query = delete(History).where(History.user_id == user_id, History.news_id == news_id)
    result = await db.execute(query)
    await db.commit()

    return result.rowcount > 0


async def clear_history(db: AsyncSession, user_id: int):
    """
    清空历史记录
    """
    query = delete(History).where(History.user_id == user_id)
    result = await db.execute(query)
    await db.commit()

    return result.rowcount or 0
