"""新闻全文搜索。

用 MySQL 8 内置的 ngram 分词器（`ft_news_search` 索引）。有几个实测出来的坑：

1. **必须用 BOOLEAN MODE + 短语查询**。
   NATURAL LANGUAGE MODE 是「或」语义：ngram 把「不存在的词xyz」切成多个 2 字片段，
   任意片段命中就算一条，实测会返回 3 条完全无关的新闻。
   改成 `+"关键词"` 后，只有片段连续出现才算命中，同一个词从 3 条降到 0 条。

2. **单字关键词一定搜不到**（ngram_token_size 默认 2），必须回退 LIKE。

3. **英文关键词可能完全命中不到**：实测 `MATCH ... AGAINST('NASA')` 的 score 是 0，
   而标题里明明有 NASA（怀疑与 innodb_ft_min_token_size=3 有关）。
   所以 MATCH 返回 0 条时也要用 LIKE 兜一次。

LIKE 的 `%kw%` 用不上索引，只在前两种兜底场景执行，全表扫一遍可接受。
"""

import re

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.news import News

# ngram_token_size 的默认值。改过 MySQL 配置的话这个常量也要跟着改
NGRAM_MIN_CHARS = 2

_MATCH_TEMPLATE = "MATCH (title, description, content) AGAINST (:{param} IN BOOLEAN MODE)"

# BOOLEAN MODE 的操作符，用户输入里出现会把查询语义搞乱，先清掉
_BOOLEAN_OPERATORS = re.compile(r'[+\-><()~*"@]')


def _to_boolean_query(keyword: str) -> str:
    """把用户输入转成 `+"词1" +"词2"` 形式的短语查询。

    清洗后如果什么都不剩（例如用户只输了 `+++`），返回空串，调用方回退 LIKE。
    """
    cleaned = _BOOLEAN_OPERATORS.sub(" ", keyword)
    terms = [term for term in cleaned.split() if term]
    return " ".join(f'+"{term}"' for term in terms)


def _like_condition(keyword: str):
    """三列 LIKE。用 contains(autoescape=True) 转义用户输入里的 % 和 _。"""
    return or_(
        News.title.contains(keyword, autoescape=True),
        News.description.contains(keyword, autoescape=True),
        News.content.contains(keyword, autoescape=True),
    )


async def _search_by_fulltext(db: AsyncSession, boolean_query: str, skip: int, limit: int):
    # 两处 MATCH 用不同的参数名，否则同一个 text 子句复用会撞绑定参数。
    # 排序表达式直接把 DESC 写进 text：TextClause 没有 .desc() 方法。
    match = text(_MATCH_TEMPLATE.format(param="kw_match")).bindparams(kw_match=boolean_query)
    score_desc = text(_MATCH_TEMPLATE.format(param="kw_score") + " DESC").bindparams(
        kw_score=boolean_query
    )

    total = (await db.execute(select(func.count(News.id)).where(match))).scalar_one()
    if not total:
        return [], 0

    stmt = (
        select(News)
        .where(match)
        .order_by(score_desc, News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return rows, total


async def _search_by_like(db: AsyncSession, keyword: str, skip: int, limit: int):
    condition = _like_condition(keyword)

    total = (await db.execute(select(func.count(News.id)).where(condition))).scalar_one()
    if not total:
        return [], 0

    stmt = (
        select(News)
        .where(condition)
        .order_by(News.publish_time.desc(), News.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return rows, total


async def search_news(db: AsyncSession, keyword: str, skip: int = 0, limit: int = 10):
    """按关键词搜索，返回 (新闻列表, 总数)。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return [], 0

    if len(keyword) >= NGRAM_MIN_CHARS:
        boolean_query = _to_boolean_query(keyword)
        if boolean_query:
            rows, total = await _search_by_fulltext(db, boolean_query, skip, limit)
            if total:
                return rows, total

    return await _search_by_like(db, keyword, skip, limit)
