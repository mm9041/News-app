from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt


class Follow(Base):
    """关注。

    一行 = 「user_id 关注了某个 target」。target 可以是作者（user）或分类（category），
    共用一张表比拆两张少一半的查询代码；代价是 target_id 不设外键，
    作者被删时读取方需要过滤不存在的目标。
    """
    __tablename__ = "follow"

    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="user_target_unique"),
        Index("idx_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="关注ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="关注者ID")
    target_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="类型：user / category")
    target_id: Mapped[int] = mapped_column(UnsignedInt, nullable=False, comment="目标ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="关注时间")

    def __repr__(self):
        return f"<Follow(user_id={self.user_id}, target={self.target_type}:{self.target_id})>"
