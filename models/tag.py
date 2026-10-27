from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt


class Tag(Base):
    """标签。与新闻是多对多，一条新闻可以挂多个标签。"""
    __tablename__ = "tag"

    __table_args__ = (
        UniqueConstraint("name", name="name_UNIQUE"),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="标签ID")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="标签名")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<Tag(id={self.id}, name={self.name})>"


class NewsTag(Base):
    """新闻-标签关联。

    `(news_id, tag_id)` 唯一索引保证不会重复挂同一个标签，
    写的时候用 INSERT IGNORE，标签重名也靠 `tag.name` 的唯一索引兜住。
    """
    __tablename__ = "news_tag"

    __table_args__ = (
        UniqueConstraint("news_id", "tag_id", name="news_tag_unique"),
        Index("fk_news_tag_tag_idx", "tag_id"),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="关联ID")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("news.id"), nullable=False, comment="新闻ID")
    tag_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("tag.id"), nullable=False, comment="标签ID")

    def __repr__(self):
        return f"<NewsTag(news_id={self.news_id}, tag_id={self.tag_id})>"
