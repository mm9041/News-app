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
        UniqueConstraint("user_id", "target_type", "target_id", "target_name", name="user_target_unique"),
        Index("idx_target", "target_type", "target_id"),
        Index("idx_follow_author", "target_type", "target_name"),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="关注ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="关注者ID")
    target_type: Mapped[str] = mapped_column(String(10), nullable=False, comment="类型：user / category")
    target_id: Mapped[int] = mapped_column(UnsignedInt, nullable=False, comment="目标ID（user/category 用，author 时为 0）")
    # 作者是字符串（「海南日报」/「Dr. Chen」），target_type=author 时用这一列
    # NOT NULL DEFAULT ""（不是可选）：唯一索引必须包含这一列，
    # 而 MySQL 的唯一索引对 NULL 不去重，会让 user/category 的关注可以重复插入
    target_name: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="作者名")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="关注时间")

    def __repr__(self):
        return f"<Follow(user_id={self.user_id}, target={self.target_type}:{self.target_id})>"
