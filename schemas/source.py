"""报纸来源相关的响应模型。"""

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import NewsItemBase


class SourceBrief(BaseModel):
    id: int
    name: str


class SourceNewsResponse(BaseModel):
    """某份报纸下的新闻列表。"""

    list: list[NewsItemBase]
    total: int
    has_more: bool = Field(alias="hasMore")
    source: SourceBrief

    model_config = ConfigDict(populate_by_name=True)
