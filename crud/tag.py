"""标签的数据访问。

标签是自由文本，用户输入什么就建什么；靠 `tag.name` 的唯一索引去重，
关联表靠 `(news_id, tag_id)` 唯一索引去重，都用 INSERT IGNORE 吞掉冲突。
"""

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.news import News
from models.tag import NewsTag, Tag

MAX_TAGS_PER_NEWS = 5


async def get_or_create_tags(db: AsyncSession, names: list[str]) -> list[int]:
    """把标签名转成 id，不存在的先创建。返回去重后的 id 列表。"""
    cleaned: list[str] = []
    for name in names:
        name = (name or "").strip()
        if name and name not in cleaned:
            cleaned.append(name)
    cleaned = cleaned[:MAX_TAGS_PER_NEWS]
    if not cleaned:
        return []

    existing = {
        row[0]: row[1]
        for row in (
            await db.execute(select(Tag.name, Tag.id).where(Tag.name.in_(cleaned)))
        ).all()
    }

    missing = [name for name in cleaned if name not in existing]
    for name in missing:
        await db.execute(insert(Tag).values(name=name).prefix_with("IGNORE"))
    if missing:
        await db.commit()
        existing = {
            row[0]: row[1]
            for row in (
                await db.execute(select(Tag.name, Tag.id).where(Tag.name.in_(cleaned)))
            ).all()
        }

    return [existing[name] for name in cleaned if name in existing]


async def set_news_tags(db: AsyncSession, news_id: int, names: list[str]) -> None:
    """整份覆盖：先清空这条新闻的标签，再按新列表写入。"""
    tag_ids = await get_or_create_tags(db, names)
    await db.execute(delete(NewsTag).where(NewsTag.news_id == news_id))
    for tag_id in tag_ids:
        await db.execute(
            insert(NewsTag).values(news_id=news_id, tag_id=tag_id).prefix_with("IGNORE")
        )
    await db.commit()


async def list_news_tags(db: AsyncSession, news_id: int) -> list[Tag]:
    """返回 Tag 对象（带 id，前端才能点进标签页）。"""
    rows = await db.execute(
        select(Tag)
        .join(NewsTag, NewsTag.tag_id == Tag.id)
        .where(NewsTag.news_id == news_id)
        .order_by(Tag.id.asc())
    )
    return list(rows.scalars().all())


async def list_by_tag(db: AsyncSession, tag_id: int, skip: int, limit: int):
    """某个标签下的新闻，按发布时间倒序。"""
    total = (
        await db.execute(
            select(func.count(NewsTag.id)).where(NewsTag.tag_id == tag_id)
        )
    ).scalar_one()

    if not total:
        return [], 0

    stmt = (
        select(News)
        .join(NewsTag, NewsTag.news_id == News.id)
        .where(NewsTag.tag_id == tag_id)
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all()), total


async def get_tag(db: AsyncSession, tag_id: int) -> Tag | None:
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    return result.scalar_one_or_none()


async def hot_tags(db: AsyncSession, limit: int = 20):
    """按引用次数排序的标签，用于「标签墙」。"""
    stmt = (
        select(Tag.id, Tag.name, func.count(NewsTag.id).label("cnt"))
        .join(NewsTag, NewsTag.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(NewsTag.id).desc(), Tag.id.asc())
        .limit(limit)
    )
    return [(row[0], row[1], row[2]) for row in (await db.execute(stmt)).all()]
