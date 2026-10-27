from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AiChatItemResponse(BaseModel):
    """一条聊天记录 = 一轮问答。"""

    id: int
    message: str
    response: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


class AiChatListResponse(BaseModel):
    """聊天记录列表接口响应模型类。"""

    list: list[AiChatItemResponse]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
