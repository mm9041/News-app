"""关注相关的请求/响应模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import NewsItemBase


class FollowRequest(BaseModel):
    target_type: Literal["user", "category", "source"] = Field(alias="targetType", description="关注类型")
    target_id: int = Field(..., ge=1, alias="targetId", description="目标ID")

    model_config = ConfigDict(populate_by_name=True)


class FollowStatusResponse(BaseModel):
    """关注/取关/状态查询的统一响应。"""

    following: bool


class FollowAuthorNewsResponse(BaseModel):
    """某个作者（报纸/人名）的新闻列表。"""

    list: list[NewsItemBase]
    total: int
    has_more: bool = Field(alias="hasMore")
    author: str

    model_config = ConfigDict(populate_by_name=True)
