"""通知的请求/响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationActor(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationItemResponse(BaseModel):
    id: int
    # comment / like
    type: str
    news_id: int = Field(alias="newsId")
    news_title: str = Field(alias="newsTitle")
    # 评论类通知才有，截断到 60 字方便列表展示
    comment_preview: Optional[str] = Field(None, alias="commentPreview")
    is_read: bool = Field(alias="isRead")
    created_at: datetime = Field(alias="createdAt")
    actor: NotificationActor

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NotificationListResponse(BaseModel):
    list: list[NotificationItemResponse]
    total: int
    unread: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)
