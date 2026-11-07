"""新闻详情的响应模型。

列表项 `NewsItemBase` 放在 `schemas/base.py`：搜索、标签页、关注流、历史、
收藏等多个模块共用同一形状。这里只放详情接口专用的结构，避免把公共底座
和单一接口契约混在一起。

对外 JSON 的 camelCase 全部由 alias 负责，路由层不再手工拼键名。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import NewsItemBase


class CategoryItem(BaseModel):
    id: int
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewsListResponse(BaseModel):
    """分类列表的响应包装。列表项复用公共的 NewsItemBase。"""

    list: list[NewsItemBase]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)


class NewsSearchResponse(NewsListResponse):
    """搜索响应：在列表包装基础上多回显本次关键词。"""

    keyword: str


class TagItem(BaseModel):
    id: int
    name: str


class RelatedNewsItem(BaseModel):
    """相关推荐：结构与列表项不同，带 content，前端只用于展示摘要区。"""

    id: int
    title: str
    content: str
    image: str | None = None
    author: str | None = None
    publish_time: datetime | None = Field(None, alias="publishTime")
    category_id: int = Field(alias="categoryId")
    views: int

    model_config = ConfigDict(populate_by_name=True)


class NewsDetailResponse(BaseModel):
    id: int
    title: str
    content: str
    image: str | None = None
    author: str | None = None
    publish_time: datetime | None = Field(None, alias="publishTime")
    category_id: int = Field(alias="categoryId")
    author_id: int | None = Field(None, alias="authorId")
    source_id: int | None = Field(None, alias="sourceId")
    views: int
    likes: int
    is_liked: bool = Field(alias="isLiked")
    tags: list[TagItem] = Field(default_factory=list)
    related_news: list[RelatedNewsItem] = Field(default_factory=list, alias="relatedNews")

    model_config = ConfigDict(populate_by_name=True)


class SuggestNewsItem(BaseModel):
    id: int
    title: str


class SuggestResponse(BaseModel):
    """输入联想：标题命中的新闻 + 名称命中的标签。"""

    news: list[SuggestNewsItem]
    tags: list[TagItem]


class NewsRecommendResponse(BaseModel):
    list: list[NewsItemBase]


class NewsLikeResponse(BaseModel):
    liked: bool
    likes: int
