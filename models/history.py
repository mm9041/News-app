from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt
from models.news import News
from models.users import User


class History(Base):
    """
    浏览历史表ORM模型
    """
    __tablename__ = 'history'

    # 创建索引
    __table_args__ = (
        Index('fk_history_user_idx', 'user_id'),
        Index('fk_history_news_idx', 'news_id'),
        Index('idx_view_time', 'view_time'),
        # 列表接口按「用户 + 浏览时间倒序 + id 倒序」分页；方向见 database.sql
        Index('idx_user_view', 'user_id', 'view_time', 'id'),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="历史ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey(User.id), nullable=False, comment="用户ID")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey(News.id), nullable=False, comment="新闻ID")
    view_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="浏览时间")

    def __repr__(self):
        return f"<History(id={self.id}, user_id={self.user_id}, news_id={self.news_id}, view_time={self.view_time})>"
