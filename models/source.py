from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.mysql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt


class Source(Base):
    """报纸来源。

    新闻的「来源」和「作者」是两个维度：作者是一篇的署名，报纸是一批新闻的出处。
    关注报纸能看到它下面所有新闻的关注流，所以单独建表而不是用字符串。
    """

    __tablename__ = "source"

    __table_args__ = (
        UniqueConstraint("name", name="name_UNIQUE"),
        {"comment": "报纸来源表"},
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="报纸ID")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="报纸名称")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<Source(id={self.id}, name={self.name})>"
