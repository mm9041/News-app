"""管理后台的请求/响应模型。

与前台 schemas 的区别：管理端**需要** content（编辑时要回填），
前台列表刻意不带正文。
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# 单个标签上限对齐 tag.name 的 VARCHAR(30)：超长会被 INSERT IGNORE 静默截断，
# 不同长标签截断后还可能撞成同一个，所以在请求校验阶段就拒掉。
TagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class AdminNewsUpsertRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="标题")
    description: str | None = Field(None, max_length=500, description="摘要")
    # 中文约 2 万字就到 TEXT 的 65535 字节上限了，这里留一点余量
    content: str = Field(..., min_length=1, max_length=20000, description="正文")
    image: str | None = Field(None, max_length=255, description="封面图 URL")
    author: str | None = Field(None, max_length=50, description="作者")
    category_id: int = Field(..., ge=1, alias="categoryId", description="分类ID")
    publish_time: datetime | None = Field(None, alias="publishTime", description="发布时间")
    # 自由文本标签，最多 5 个；不存在的会自动创建
    tags: list[TagName] = Field(default_factory=list, max_length=5, description="标签")

    model_config = ConfigDict(populate_by_name=True)


class AdminNewsItemResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    content: str
    image: str | None = None
    author: str | None = None
    category_id: int = Field(alias="categoryId")
    views: int
    publish_time: datetime | None = Field(None, alias="publishTime")
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
    nickname: str | None = None
    avatar: str | None = None
    gender: str | None = None
    bio: str | None = None
    phone: str | None = None
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


class StatsOverview(BaseModel):
    news: int
    comments: int
    users: int
    views: int


class StatsTrendItem(BaseModel):
    date: str
    news: int
    comments: int


class StatsCategoryItem(BaseModel):
    name: str
    news: int
    views: int


class StatsTopNewsItem(BaseModel):
    id: int
    title: str
    views: int
    category_id: int = Field(alias="categoryId")

    model_config = ConfigDict(populate_by_name=True)


class AdminStatsResponse(BaseModel):
    """看板响应。对外 camelCase 靠 alias，对外契约与原来手工拼的 dict 完全一致。"""

    overview: StatsOverview
    trend: list[StatsTrendItem]
    categories: list[StatsCategoryItem]
    top_news: list[StatsTopNewsItem] = Field(alias="topNews")

    model_config = ConfigDict(populate_by_name=True)


class AdminFlagRequest(BaseModel):
    is_admin: bool = Field(..., alias="isAdmin")

    model_config = ConfigDict(populate_by_name=True)
