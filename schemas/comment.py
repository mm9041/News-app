"""评论的请求/响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentAddRequest(BaseModel):
    news_id: int = Field(..., ge=1, alias="newsId", description="新闻ID")
    content: str = Field(..., min_length=1, max_length=500, description="评论内容")

    model_config = ConfigDict(populate_by_name=True)


class CommentUser(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CommentItemResponse(BaseModel):
    id: int
    content: str
    created_at: datetime = Field(alias="createdAt")
    user: CommentUser
    # 由后端算好（本人或管理员），前端只照着渲染，避免两边各写一套规则
    can_delete: bool = Field(False, alias="canDelete")

    model_config = ConfigDict(populate_by_name=True)


class CommentListResponse(BaseModel):
    list: list[CommentItemResponse]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)
