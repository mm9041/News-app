"""评论的请求/响应模型。

只做两级：一级评论（parentId 为空）+ 它下面的回复。
`replies` 只出现在一级评论上，回复自身不再嵌套，避免无限递归渲染。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentAddRequest(BaseModel):
    news_id: int = Field(..., ge=1, alias="newsId", description="新闻ID")
    content: str = Field(..., min_length=1, max_length=500, description="评论内容")
    # 传了就表示这是回复；指向任意一条评论（回复的回复会归到所属的一级评论）
    parent_id: int | None = Field(None, ge=1, alias="parentId", description="父评论ID")

    model_config = ConfigDict(populate_by_name=True)


class CommentUser(BaseModel):
    id: int
    username: str
    nickname: str | None = None
    avatar: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CommentReply(BaseModel):
    """回复（二级）。不带 replies。"""

    id: int
    content: str
    created_at: datetime = Field(alias="createdAt")
    user: CommentUser
    can_delete: bool = Field(False, alias="canDelete")
    parent_id: int | None = Field(None, alias="parentId")
    # 被回复人的昵称，用于渲染「回复 @某某」
    reply_to: str | None = Field(None, alias="replyTo")

    model_config = ConfigDict(populate_by_name=True)


class CommentItemResponse(CommentReply):
    """一级评论，带它下面的回复。"""

    replies: list[CommentReply] = Field(default_factory=list)


class CommentListResponse(BaseModel):
    list: list[CommentItemResponse]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)


class CommentCreatedResponse(BaseModel):
    id: int
