from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt


class AiChat(Base):
    """AI 聊天记录表 ORM 模型。

    注意：这张表只有 created_at，没有 updated_at，
    所以**不能**继承 TimestampMixin（继承了会映射出不存在的列 → 1054）。

    外键用字符串 "user.id" 而不是 User.id 对象，避免 models 之间产生循环导入。
    列名与 database.sql 里的 `ai_chat` 逐字对齐。
    """
    __tablename__ = "ai_chat"

    __table_args__ = (
        Index("fk_ai_chat_user_idx", "user_id"),
        Index("idx_created_at", "created_at"),
        # 历史分页按「用户 + 时间倒序 + id 倒序」；方向见 database.sql
        Index("idx_user_created", "user_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="聊天记录ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="用户ID")
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="用户消息")
    response: Mapped[str] = mapped_column(Text, nullable=False, comment="AI回复")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<AiChat(id={self.id}, user_id={self.user_id}, created_at={self.created_at})>"
