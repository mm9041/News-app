from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import TIMESTAMP

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
        # 一个人对同一篇新闻只该有一条历史记录。有了这条唯一索引，
        # add_history 才能用 ON DUPLICATE KEY UPDATE 做幂等 upsert；
        # 没有它的话「先查后插」在并发下会插出重复行。
        UniqueConstraint('user_id', 'news_id', name='user_news_unique'),
        # 这里原来还有一条单列索引 `fk_history_user_idx (user_id)`，已删：
        # user_id 是上面唯一索引和 idx_user_view 的**左前缀**，B+ 树本来就按它排好序，
        # 单列索引在查询里从未被选中（EXPLAIN 验证），只增加写入维护成本。
        # 外键也不需要它 —— InnoDB 只要求外键列上有可用索引，左前缀满足。
        Index('fk_history_news_idx', 'news_id'),
        Index('idx_view_time', 'view_time'),
        # 列表接口按「用户 + 浏览时间倒序 + id 倒序」分页；方向见 database.sql
        Index('idx_user_view', 'user_id', 'view_time', 'id'),
        {"comment": "浏览历史表"},
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="历史ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey(User.id), nullable=False, comment="用户ID")
    news_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey(News.id), nullable=False, comment="新闻ID")
    view_time: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, nullable=False, comment="浏览时间")

    def __repr__(self):
        return f"<History(id={self.id}, user_id={self.user_id}, news_id={self.news_id}, view_time={self.view_time})>"
