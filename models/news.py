from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Index, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import TIMESTAMP

from models.base import Base, TimestampMixin, UnsignedInt
# news.source_id 的 ForeignKey 指向 source 表：必须让 SQLAlchemy 的 metadata
# 看到这张表，否则 News 的任何 flush 都会报 NoReferencedTableError
from models.source import Source  # noqa: F401


class Category(Base, TimestampMixin):
    __tablename__ = "news_category"
    # 与 database.sql 的 `name_UNIQUE` 对齐（原来只写了列上 unique=True，
    # 约束没有名字，和库里的索引名对不上）
    __table_args__ = (
        UniqueConstraint("name", name="name_UNIQUE"),
        {"comment": "新闻分类表"},
    )
    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="分类ID")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="分类名称")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="排序顺序")

    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name}, sort_order={self.sort_order})>"


class News(Base, TimestampMixin):
    __tablename__ = "news"
    __table_args__ = (
        # 添加索引，提升查询速度
        Index("fk_news_category_idx", "category_id"),  # 分类ID外键索引
        Index("idx_publish_time", "publish_time"),  # 发布时间索引
        # 列表接口的「分类 + 发布时间倒序 + id 倒序」联合索引。
        # ⚠️ 方向信息写在 database.sql 里（`publish_time DESC, id DESC`），
        # metadata 里只声明列，避免 create_all 与手工 DDL 打架。
        Index("idx_category_publish", "category_id", "publish_time", "id"),
        # 中文全文检索：ngram 分词器（MySQL 8 内置）。
        # ngram_token_size 默认 2，单字关键词 MATCH 不到，应用层会回退 LIKE。
        Index("ft_news_search", "title", "description", "content",
              mysql_prefix="FULLTEXT", mysql_with_parser="ngram"),
        # 发布者：后台创建新闻时记当前管理员，用来给「我的新闻被评论/点赞」发通知。
        # 历史种子数据这一列是 NULL，不会产生通知。
        Index("fk_news_user_idx", "user_id"),
        Index("idx_news_source", "source_id"),
        {"comment": "新闻表"},
    )
    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="新闻ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻标题")
    description: Mapped[Optional[str]] = mapped_column(String(500), comment="新闻简介")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="新闻内容")
    image: Mapped[Optional[str]] = mapped_column(String(255), comment="封面图片URL")
    author: Mapped[Optional[str]] = mapped_column(String(50), comment="作者")
    # 报纸来源：作者是一篇的署名，报纸是一批新闻的出处；关注报纸能看到关注流
    source_id: Mapped[Optional[int]] = mapped_column(
        UnsignedInt, ForeignKey("source.id", ondelete="SET NULL"), nullable=True, comment="报纸来源ID"
    )
    category_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey("news_category.id"), nullable=False, comment="分类ID")
    user_id: Mapped[Optional[int]] = mapped_column(
        UnsignedInt, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, comment="发布者ID"
    )
    views: Mapped[int] = mapped_column(UnsignedInt, default=0, nullable=False, comment="浏览量")
    publish_time: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, comment="发布时间")

    def __repr__(self):
        return f"<News(id={self.id}, title={self.title}, views={self.views})>"
