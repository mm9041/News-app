import asyncio
import random
from datetime import datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cache import view_counter
from cache.news_cache import (
    DETAIL_CACHE_PREFIX,
    get_cached_categories,
    get_cached_news_list,
    set_cache_categories,
    set_cache_news_list,
)
from config.cache_conf import get_json_cache, redis_client, set_cache
from crud import tag as tag_crud
from crud.news_views import apply_view_deltas
from models.news import Category, News
from schemas.base import NewsItemBase
from utils.logger import get_logger

logger = get_logger(__name__)

DETAIL_LOCK_PREFIX = "lock:news:detail:"
# 详情页的「标签 + 相关推荐」单独一个 key：只有详情接口需要它，
# 点赞/评论那条路径不该为它多查两次库。
EXTRAS_CACHE_PREFIX = "news:extras:"
DETAIL_TTL_BASE = 120
DETAIL_TTL_JITTER = 60  # 抖动范围，避免同批 key 同时过期（雪崩）
NULL_TTL = 30  # 空值缓存，防穿透
LOCK_TTL = 3
LOCK_WAIT_ROUNDS = 10
LOCK_WAIT_INTERVAL = 0.05


async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100):
    cached_categories = await get_cached_categories()
    if cached_categories:
        return cached_categories
    stmt = select(Category).offset(skip).limit(limit)
    result = await db.execute(stmt)
    categories = result.scalars().all()
    if categories:
        categories = jsonable_encoder(categories)
        await set_cache_categories(categories, expire=7200)
    return categories


async def get_news_list(db: AsyncSession, category_id: int, skip: int = 0, limit: int = 100) -> list[NewsItemBase]:
    """分页取某个分类的新闻列表。

    两条路径（缓存命中 / 回源查库）都返回同一个 NewsItemBase 列表。
    之前命中缓存时用 `News(**cache_item)` 重建 ORM 对象，而缓存里存的是
    NewsItemBase 的字段（不含 content），于是「冷缓存多返回 content、热缓存不返回」，
    响应体随缓存状态漂移。统一成 schema 后契约稳定，输出也统一成 camelCase，
    前端 NewsItem 里用的 publishTime 才对得上。
    """
    page = skip // limit + 1
    cached_list = await get_cached_news_list(category_id, page, limit)
    if cached_list:
        # 缓存里存的是库里的原值，这里再叠加尚未回写的阅读量增量
        return await apply_view_deltas([NewsItemBase.model_validate(item) for item in cached_list])

    stmt = (
        select(News)
        .where(News.category_id == category_id)
        # 不显式排序时，分页顺序取决于存储引擎/执行计划，翻页可能重复或漏条；
        # id 做次级键是为了 publish_time 相同（同一天批量导入）时顺序仍然稳定。
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = [NewsItemBase.model_validate(row) for row in result.scalars().all()]
    if items:
        await set_cache_news_list(
            category_id,
            page,
            limit,
            [item.model_dump(mode="json", by_alias=False) for item in items],
        )
    return await apply_view_deltas(items)


async def get_news_count(db: AsyncSession, category_id: int):
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    result = await db.execute(stmt)
    return result.scalar_one()


async def news_exists(db: AsyncSession, news_id: int) -> bool:
    """只查主键在不在，给收藏 / 浏览历史这类写操作做 404 前置判断。

    不复用 `get_news_detail`：那个会把整行塞进详情缓存，
    而「收藏一个不存在的 id」完全不值得占一份缓存。
    """
    result = await db.execute(select(News.id).where(News.id == news_id))
    return result.scalar_one_or_none() is not None


def _dump_news(news: News) -> dict:
    return {
        "id": news.id,
        "title": news.title,
        "description": news.description,
        "content": news.content,
        "image": news.image,
        "author": news.author,
        "category_id": news.category_id,
        "user_id": news.user_id,
        "source_id": news.source_id,
        "views": news.views,
        "publish_time": news.publish_time.isoformat() if news.publish_time else None,
        "created_at": news.created_at.isoformat() if news.created_at else None,
        "updated_at": news.updated_at.isoformat() if news.updated_at else None,
    }


def _load_news(payload: dict) -> News:
    data = dict(payload)
    for field in ("publish_time", "created_at", "updated_at"):
        value = data.get(field)
        if isinstance(value, str):
            data[field] = datetime.fromisoformat(value)
    return News(**data)


async def get_news_detail(db: AsyncSession, news_id: int):
    """新闻详情（带缓存）。

    缓存三件套都在这一个函数里：
    - 穿透：查不到的 id 也写一个 30 秒的空标记，避免反复打库
    - 击穿：缓存过期的瞬间只放一个请求回源，其余等它写回（Redis 互斥锁）
    - 雪崩：TTL = 基础值 + 随机抖动，同批 key 不会同时失效

    ⚠️ 缓存里的 views 是快照，比库里的真实值旧。这里可以接受：
    阅读量展示走「库内值 + Redis 增量」，而 Redis 一旦不可用，缓存本身也读不到，
    所以不会出现拿旧值覆盖库的情况。
    """
    key = f"{DETAIL_CACHE_PREFIX}{news_id}"

    cached = await get_json_cache(key)
    if cached is not None:
        if cached.get("__null__"):
            return None
        try:
            return _load_news(cached)
        except Exception:
            # 结构变了（比如新增了列）就当未命中，别让旧缓存把请求打挂
            logger.warning("详情缓存解析失败，回源：news_id=%s", news_id)

    lock_key = f"{DETAIL_LOCK_PREFIX}{news_id}"
    locked = False
    try:
        locked = bool(await redis_client.set(lock_key, "1", nx=True, ex=LOCK_TTL))
    except Exception:
        locked = False

    if not locked:
        # 别人正在回源，短暂等待并重试缓存
        for _ in range(LOCK_WAIT_ROUNDS):
            await asyncio.sleep(LOCK_WAIT_INTERVAL)
            cached = await get_json_cache(key)
            if cached is not None:
                return None if cached.get("__null__") else _load_news(cached)
        # 等不到就自己查：宁可多一次查询，也不能让请求卡死

    try:
        result = await db.execute(select(News).where(News.id == news_id))
        news = result.scalar_one_or_none()

        if news is None:
            await set_cache(key, {"__null__": True}, NULL_TTL)
            return None

        await set_cache(key, _dump_news(news), DETAIL_TTL_BASE + random.randint(0, DETAIL_TTL_JITTER))
        return news
    finally:
        if locked:
            try:
                await redis_client.delete(lock_key)
            except Exception:
                pass


async def invalidate_news_detail(news_id: int) -> None:
    """后台改/删新闻后调用，否则详情最多 3 分钟仍是旧的。

    标签和「相关推荐」跟着详情一起失效：改标题、改分类、换标签都会影响它们。
    """
    try:
        await redis_client.delete(f"{DETAIL_CACHE_PREFIX}{news_id}", f"{EXTRAS_CACHE_PREFIX}{news_id}")
    except Exception as e:
        logger.warning("清理详情缓存失败（news_id=%s）：%s", news_id, e)


async def increase_news_views(db: AsyncSession, news_id: int, current_views: int) -> int:
    """浏览 +1，返回本次请求应当展示的阅读量。

    正常路径只动 Redis（`INCR`），不产生 UPDATE、也不清列表缓存；
    增量由后台任务定时批量写回数据库。Redis 不可用时退回直写数据库：
    缓存层可以挂，阅读量不能停。

    `current_views` 传查询时读到的库内值，返回 `库内值 + 未回写增量`。
    不能把自增后的值写回 ORM 对象再读，那样在并发下会彼此覆盖。
    """
    delta = await view_counter.increase(news_id)
    if delta is not None:
        return current_views + delta

    stmt = update(News).where(News.id == news_id).values(views=News.views + 1)
    await db.execute(stmt)
    await db.commit()
    return current_views + 1


async def _fetch_related_rows(db: AsyncSession, news_id: int, category_id: int, limit: int = 5) -> list[dict]:
    """查库拿相关推荐，`views` 是**库内原值**（不在这一层叠加 Redis 增量）。

    缓存里存的必须是原值：存叠加后的值，命中缓存时会把同一份增量再加一遍。
    """
    stmt = (
        select(News)
        .where(
            News.category_id == category_id,
            News.id != news_id,
        )
        .order_by(News.views.desc(), News.publish_time.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": news.id,
            "title": news.title,
            "content": news.content,
            "image": news.image,
            "author": news.author,
            # 必须转成字符串再进缓存：json.dumps 不认 datetime，
            # 写缓存会静默失败（只留一条 warning），缓存等于没生效。
            "publishTime": news.publish_time.isoformat() if news.publish_time else None,
            "categoryId": news.category_id,
            "views": news.views,
        }
        for news in result.scalars().all()
    ]


async def _apply_related_view_deltas(rows: list[dict]) -> list[dict]:
    """把还没回写的阅读量增量叠到相关推荐上（只改内存，不写回缓存）。

    不叠加的话，详情页的相关推荐会比列表页的阅读量小 —— 之前踩过。
    """
    if not rows:
        return rows
    deltas = await view_counter.get_deltas([row["id"] for row in rows])
    for row in rows:
        delta = deltas.get(row["id"])
        if delta:
            row["views"] += delta
    return rows


async def get_detail_extras(db: AsyncSession, news_id: int, category_id: int) -> dict:
    """详情页的「标签 + 相关推荐」，带独立缓存。

    这两块内容变动很慢，却让每次详情请求各付一次查库。缓存后命中路径上
    只剩「点赞」一次数据库往返（原来是 3 次），这是详情接口延迟的大头。

    ⚠️ 相关推荐是按 `views` 降序排的，所以缓存会有最多一个 TTL 的滞后
    （120~180s）。这是推荐位，不是正文，可以接受；要更快就调小 TTL。
    """
    key = f"{EXTRAS_CACHE_PREFIX}{news_id}"

    cached = await get_json_cache(key)
    if cached is not None:
        # 深拷贝一份再叠加增量，别把缓存里那份共享 dict 改脏
        cached = {"tags": cached.get("tags", []), "related": [dict(row) for row in cached.get("related", [])]}
        cached["related"] = await _apply_related_view_deltas(cached["related"])
        return cached

    tag_rows = await tag_crud.list_news_tags(db, news_id)
    payload = {
        "tags": [{"id": tag.id, "name": tag.name} for tag in tag_rows],
        "related": await _fetch_related_rows(db, news_id, category_id),
    }
    await set_cache(key, payload, DETAIL_TTL_BASE + random.randint(0, DETAIL_TTL_JITTER))
    return {
        "tags": payload["tags"],
        "related": await _apply_related_view_deltas([dict(row) for row in payload["related"]]),
    }
