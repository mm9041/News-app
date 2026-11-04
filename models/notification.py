from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import TIMESTAMP

from models.base import Base, UnsignedInt


class Notification(Base):
    """站内通知。

    一条记录 = 「某人（actor）对我的内容做了某事（type）」。
    目前只覆盖两类：别人评论了我发布的新闻、别人点赞了我发布的新闻。

    接收者是新闻的 `user_id`（发布者）。历史种子新闻没有发布者，
    所以对它们的互动不会产生通知 —— 这是数据决定的，不是逻辑漏了。
    """
    __tablename__ = "notification"

    __table_args__ = (
        # 列表按「用户 + 未读 + 时间倒序」查，未读数也走这个索引的前缀
        Index("idx_notification_user", "user_id", "is_read", "created_at", "id"),
        Index("fk_notification_actor_idx", "actor_id"),
        Index("fk_notification_news_idx", "news_id"),
        {"comment": "消息通知表"},
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="通知ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="接收者ID")
    actor_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("user.id"), nullable=False, comment="触发者ID")
    type: Mapped[str] = mapped_column(String(20), nullable=False, comment="类型：comment / like")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("news.id"), nullable=False, comment="相关新闻ID")
    comment_id: Mapped[Optional[int]] = mapped_column(
        UnsignedInt, ForeignKey("news_comment.id", ondelete="SET NULL"), nullable=True, comment="相关评论ID"
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否已读")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"
