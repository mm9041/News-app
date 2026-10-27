from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt


class NewsLike(Base):
    """新闻点赞。

    `(user_id, news_id)` 唯一索引保证一人一条；重复点赞靠 INSERT IGNORE 吃掉，
    所以接口是幂等的（前端重试不会多算）。

    点赞总数不冗余到 `news` 表：那会引出「计数什么时候减、缓存怎么失效」
    一整套问题，而单条新闻的 COUNT 走 `idx_news_like_news`，代价很低。
    """
    __tablename__ = "news_like"

    __table_args__ = (
        UniqueConstraint("user_id", "news_id", name="user_news_like_unique"),
        Index("idx_news_like_news", "news_id"),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="点赞ID")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("news.id"), nullable=False, comment="新闻ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="用户ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="点赞时间")

    def __repr__(self):
        return f"<NewsLike(news_id={self.news_id}, user_id={self.user_id})>"
