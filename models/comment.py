from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import TIMESTAMP

from models.base import Base, UnsignedInt


class NewsComment(Base):
    """新闻评论。

    这张表只有 created_at，没有 updated_at，所以不能继承 TimestampMixin
    （继承会映射出不存在的列 → 1054）。

    评论不支持编辑，也不做软删除：删除就是物理删除。
    新闻或用户被删时由外键 CASCADE 一起清掉。
    """
    __tablename__ = "news_comment"

    __table_args__ = (
        # 详情页按「新闻 + 时间倒序 + id 倒序」分页。
        # 方向（DESC）只在 database.sql 里表达，metadata 只声明列，
        # 避免 create_all 与手工 DDL 打架。
        Index("idx_news_created", "news_id", "created_at", "id"),
        Index("fk_news_comment_user_idx", "user_id"),
        Index("fk_comment_parent_idx", "parent_id"),
        Index("fk_comment_reply_to_idx", "reply_to_user_id"),
        {"comment": "新闻评论表"},
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="评论ID")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("news.id"), nullable=False, comment="新闻ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="用户ID")
    # 只有两级：一级评论 parent_id 为空，回复指向所属的一级评论。
    # 回复不再被回复（前端拿 parentId 渲染缩进，但不再往下嵌套）。
    parent_id: Mapped[Optional[int]] = mapped_column(
        UnsignedInt, ForeignKey("news_comment.id", ondelete="CASCADE"), nullable=True, comment="父评论ID"
    )
    # 回复某条回复时，parent_id 仍然指向所属的一级评论（避免多层嵌套），
    # 真正的「回复给谁」记在这里，用来显示「回复 @某某」。
    reply_to_user_id: Mapped[Optional[int]] = mapped_column(
        UnsignedInt, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, comment="被回复的用户ID"
    )
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="评论内容")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<NewsComment(id={self.id}, news_id={self.news_id}, user_id={self.user_id})>"
