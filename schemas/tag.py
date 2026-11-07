"""标签相关的响应模型。"""

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import NewsItemBase


class TagBrief(BaseModel):
    id: int
    name: str


class TagHotItem(TagBrief):
    count: int


class TagNewsResponse(BaseModel):
    """某个标签下的新闻列表。"""

    list: list[NewsItemBase]
    total: int
    has_more: bool = Field(alias="hasMore")
    tag: TagBrief

    model_config = ConfigDict(populate_by_name=True)
