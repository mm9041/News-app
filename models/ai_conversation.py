from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import TIMESTAMP

from models.base import Base, UnsignedInt


class AiConversation(Base):
    """AI 会话。

    一个会话下有多轮问答（ai_chat 通过 conversation_id 关联）。
    `updated_at` 在每次追问时手动 touch —— MySQL 的 ON UPDATE CURRENT_TIMESTAMP
    只在 UPDATE 本表时触发，插 ai_chat 不会连带更新它。
    """
    __tablename__ = "ai_conversation"

    __table_args__ = (
        # 列表按「用户 + 最后活跃倒序」，id 做次级键避免同秒并列
        Index("idx_conv_user", "user_id", "updated_at", "id"),
        {"comment": "AI会话表"},
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="会话ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="用户ID")
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="新对话", comment="会话标题（取首条提问）")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, default=datetime.now, onupdate=datetime.now, nullable=False, comment="最后活跃时间"
    )

    def __repr__(self):
        return f"<AiConversation(id={self.id}, user_id={self.user_id}, title={self.title})>"
