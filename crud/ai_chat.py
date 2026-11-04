from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_chat import AiChat
from models.ai_conversation import AiConversation

# MySQL 的 TEXT 上限是 65535 **字节**（不是字符）。utf8mb4 下一个汉字占 3 字节，
# 也就是说中文只能存两万出头。模型的长回答很容易超，落库前先按字节截断，
# 否则一条超长回答会让整次请求报 1406 Data too long 变成 500。
MAX_TEXT_BYTES = 60000
TRUNCATED_SUFFIX = "…（内容过长，已截断）"


def truncate_by_bytes(text: str, max_bytes: int = MAX_TEXT_BYTES) -> str:
    """按 UTF-8 字节数截断，不会把多字节字符切成乱码。"""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    # errors="ignore" 丢掉被切在中间的那个残缺字符
    return raw[:max_bytes].decode("utf-8", "ignore") + TRUNCATED_SUFFIX


async def save_chat(
        db: AsyncSession,
        user_id: int,
        message: str,
        response: str,
        conversation_id: Optional[int] = None,
) -> AiChat:
    """存一轮问答：用户问的进 message，AI 答的进 response。"""
    record = AiChat(
        user_id=user_id,
        conversation_id=conversation_id,
        message=truncate_by_bytes(message),
        response=truncate_by_bytes(response),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------- 会话


async def create_conversation(db: AsyncSession, user_id: int, title: str) -> AiConversation:
    title = (title or "").strip().replace("\n", " ")[:100] or "新对话"
    conv = AiConversation(user_id=user_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation(db: AsyncSession, conversation_id: int, user_id: int) -> AiConversation | None:
    """带 user_id 条件查，别人的会话查不到（也就无法越权）。"""
    result = await db.execute(
        select(AiConversation).where(
            AiConversation.id == conversation_id, AiConversation.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_conversations(db: AsyncSession, user_id: int, skip: int, limit: int):
    """只返回真正有消息的会话（点过「新对话」但没提问的不显示）。"""
    joined = (
        select(AiConversation.id)
        .join(AiChat, AiChat.conversation_id == AiConversation.id)
        .where(AiConversation.user_id == user_id)
        .group_by(AiConversation.id)
    )
    total = (
        await db.execute(select(func.count()).select_from(joined.subquery()))
    ).scalar_one()

    if not total:
        return [], 0

    stmt = (
        select(AiConversation, func.count(AiChat.id))
        .join(AiChat, AiChat.conversation_id == AiConversation.id)
        .where(AiConversation.user_id == user_id)
        .group_by(AiConversation.id)
        .order_by(AiConversation.updated_at.desc(), AiConversation.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows], total


async def list_messages(db: AsyncSession, conversation_id: int) -> list[dict]:
    """把一个会话的问答展开成消息流：每轮拆成 user + assistant 两条。"""
    result = await db.execute(
        select(AiChat)
        .where(AiChat.conversation_id == conversation_id)
        .order_by(AiChat.created_at.asc(), AiChat.id.asc())
    )
    messages: list[dict] = []
    for chat in result.scalars().all():
        messages.append({"role": "user", "content": chat.message, "createdAt": chat.created_at})
        messages.append({"role": "assistant", "content": chat.response, "createdAt": chat.created_at})
    return messages


async def touch_conversation(db: AsyncSession, conversation_id: int) -> None:
    """手动更新活跃时间：插 ai_chat 不会触发本表的 ON UPDATE。"""
    await db.execute(
        update(AiConversation)
        .where(AiConversation.id == conversation_id)
        .values(updated_at=datetime.now())
    )
    await db.commit()


async def delete_conversation(db: AsyncSession, conv: AiConversation) -> None:
    # ai_chat.conversation_id 是 CASCADE，消息会一起删
    await db.delete(conv)
    await db.commit()


async def get_chat_list(db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20):
    """分页取某个用户的聊天记录，按时间**倒序**返回 (记录列表, 总数)。

    倒序是为了分页语义正确：page=1 就是最新的那一屏，以后要加"加载更早的"
    直接翻 page 就行。前端展示时自己反转成时间正序。

    排序带上 id 做次级键：created_at 是 TIMESTAMP（秒精度），同一秒内的两轮问答
    只按 created_at 排会得到不确定的顺序。
    """
    count_result = await db.execute(
        select(func.count(AiChat.id)).where(AiChat.user_id == user_id)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(AiChat)
        .where(AiChat.user_id == user_id)
        .order_by(AiChat.created_at.desc(), AiChat.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all(), total
