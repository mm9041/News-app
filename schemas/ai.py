"""AI 对话相关的请求/响应模型。

会话（conversation）是后加的一层：一个会话下有多轮问答（ai_chat 一行一轮）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AiChatItemResponse(BaseModel):
    """一条聊天记录 = 一轮问答。"""

    id: int
    message: str
    response: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AiChatListResponse(BaseModel):
    """聊天记录列表接口响应模型类。"""

    list: list[AiChatItemResponse]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(None, max_length=100, description="会话标题，默认取首条提问")
    model_config = ConfigDict(populate_by_name=True)


class ConversationItemResponse(BaseModel):
    id: int
    title: str
    message_count: int = Field(alias="messageCount")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ConversationListResponse(BaseModel):
    list: list[ConversationItemResponse]
    total: int
    has_more: bool = Field(alias="hasMore")

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageItem(BaseModel):
    """会话内的一条消息（user / assistant 各一条）。"""

    role: str
    content: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class ConversationDetailResponse(BaseModel):
    id: int
    title: str
    messages: list[ChatMessageItem]

    model_config = ConfigDict(populate_by_name=True)
