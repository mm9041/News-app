from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_chat import AiChat

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


async def save_chat(db: AsyncSession, user_id: int, message: str, response: str) -> AiChat:
    """存一轮问答：用户问的进 message，AI 答的进 response。"""
    record = AiChat(
        user_id=user_id,
        message=truncate_by_bytes(message),
        response=truncate_by_bytes(response),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


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
