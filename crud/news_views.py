"""阅读量的读侧与回写侧。

- `apply_view_deltas` / `get_display_views`：把 Redis 里尚未回写的增量叠加到返回值上。
- `flush_view_deltas`：后台定时把增量批量写回 news.views。

缓存里存的必须是**数据库原值**。如果把叠加过增量的值写进缓存，下次命中时
同一份增量会被再加一遍，阅读量就会凭空翻倍。
"""

from sqlalchemy import update

from cache import view_counter
from cache.news_cache import delete_detail_caches
from config.db_conf import AsyncSessionLocal
from models.news import News
from schemas.base import NewsItemBase


async def apply_view_deltas(items: list[NewsItemBase]) -> list[NewsItemBase]:
    """给一批列表项叠加未回写的阅读量增量（只改内存对象，不改缓存）。"""
    if not items:
        return items
    deltas = await view_counter.get_deltas([item.id for item in items])
    if not deltas:
        return items
    for item in items:
        delta = deltas.get(item.id)
        if delta:
            item.views += delta
    return items


async def get_display_views(news_id: int, db_views: int) -> int:
    """单条新闻对外展示的阅读量 = 库里的值 + 未回写的增量。"""
    deltas = await view_counter.get_deltas([news_id])
    return db_views + deltas.get(news_id, 0)


async def flush_view_deltas(batch_size: int = 500) -> int:
    """把最多 batch_size 条增量写回数据库，返回本次刷新的新闻条数。

    顺序很重要，三步不能交换：

    1. 先 commit —— 库变成新值；
    2. 再删详情缓存 —— 详情缓存里存的是旧快照，不删的话「快照 + 增量」
       会在增量被清零后掉回快照值，表现为阅读量倒退（实测 7485 → 7484）。
       放在 commit 之后：这期间回源拿到的是新值，缓存仍是旧快照 + 待回写增量，两者相等；
    3. 最后 DECRBY —— 反向操作（先扣减后写库）一旦写库失败，这批阅读量就永久丢了；
       而先写库后扣减，最坏情况只是进程在两步之间崩掉导致少量重复计数。

    为什么不用 DEL 而用 DECRBY：从「读出增量」到「写库成功」之间可能又有新的
    INCR 进来，DEL 会把那部分一起丢掉。
    """
    snapshot = await view_counter.snapshot_deltas(batch_size)
    if not snapshot:
        return 0

    async with AsyncSessionLocal() as db:
        try:
            for news_id, delta in snapshot.items():
                await db.execute(update(News).where(News.id == news_id).values(views=News.views + delta))
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    await delete_detail_caches(snapshot.keys())

    for news_id, delta in snapshot.items():
        await view_counter.commit(news_id, delta)
    return len(snapshot)
