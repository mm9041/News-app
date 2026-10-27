from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

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
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="评论ID")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("news.id"), nullable=False, comment="新闻ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="用户ID")
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="评论内容")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<NewsComment(id={self.id}, news_id={self.news_id}, user_id={self.user_id})>"
