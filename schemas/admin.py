"""管理后台的请求/响应模型。

与前台 schemas 的区别：管理端**需要** content（编辑时要回填），
前台列表刻意不带正文。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminNewsUpsertRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="标题")
    description: Optional[str] = Field(None, max_length=500, description="摘要")
    # 中文约 2 万字就到 TEXT 的 65535 字节上限了，这里留一点余量
    content: str = Field(..., min_length=1, max_length=20000, description="正文")
    image: Optional[str] = Field(None, max_length=255, description="封面图 URL")
    author: Optional[str] = Field(None, max_length=50, description="作者")
    category_id: int = Field(..., ge=1, alias="categoryId", description="分类ID")
    publish_time: Optional[datetime] = Field(None, alias="publishTime", description="发布时间")
    # 自由文本标签，最多 5 个；不存在的会自动创建
    tags: list[str] = Field(default_factory=list, max_length=5, description="标签")

    model_config = ConfigDict(populate_by_name=True)


class AdminNewsItemResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    content: str
    image: Optional[str] = None
    author: Optional[str] = None
    category_id: int = Field(alias="categoryId")
    views: int
    publish_time: Optional[datetime] = Field(None, alias="publishTime")
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AdminNewsListResponse(BaseModel):
    list: list[AdminNewsItemResponse]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AdminUserItemResponse(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    is_admin: bool = Field(alias="isAdmin")
    banned: bool
    comment_count: int = Field(alias="commentCount")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class AdminUserListResponse(BaseModel):
    list: list[AdminUserItemResponse]
    total: int

    model_config = ConfigDict(populate_by_name=True)


class BanRequest(BaseModel):
    banned: bool

    model_config = ConfigDict(populate_by_name=True)


class AdminFlagRequest(BaseModel):
    is_admin: bool = Field(..., alias="isAdmin")

    model_config = ConfigDict(populate_by_name=True)
