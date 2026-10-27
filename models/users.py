from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, UnsignedInt


class User(Base):
    """
    用户信息表ORM模型
    """
    __tablename__ = 'user'

    # 唯一约束的名字与 database.sql 里的 `username_UNIQUE` / `phone_UNIQUE` 逐字对齐。
    # 这里原本写成 Index(...) + 列上 unique=True，等于同一列声明了两遍唯一性：
    # metadata 里会出现两个对象，将来接 Alembic autogenerate 会生成多余的 DDL。
    __table_args__ = (
        UniqueConstraint('username', name='username_UNIQUE'),
        UniqueConstraint('phone', name='phone_UNIQUE'),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), nullable=False, comment="用户名")
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码（加密存储）")
    nickname: Mapped[Optional[str]] = mapped_column(String(50), comment="昵称")
    avatar: Mapped[Optional[str]] = mapped_column(String(255), comment="头像URL",
                                                  default='https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg')
    gender: Mapped[Optional[str]] = mapped_column(Enum('male', 'female', 'unknown'), comment="性别", default='unknown')
    bio: Mapped[Optional[str]] = mapped_column(String(500), comment="个人简介", default='这个人很懒，什么都没留下')
    phone: Mapped[Optional[str]] = mapped_column(String(20), comment="手机号")
    # 管理后台的准入标记。设为 True 的方式见 scripts/make_admin.py
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否管理员")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,comment="更新时间")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', nickname='{self.nickname}')>"


class UserToken(Base):
    """
    用户令牌表ORM模型

    注意：`token` 列存的是明文的 sha256 摘要，不是 token 本身 ——
    库泄露时不能直接拿去冒充用户。生成/校验见 `crud/users.py`。
    """
    __tablename__ = 'user_token'

    __table_args__ = (
        UniqueConstraint('token', name='token_UNIQUE'),
        Index('fk_user_token_user_idx', 'user_id'),
    )

    id: Mapped[int] = mapped_column(UnsignedInt, primary_key=True, autoincrement=True, comment="令牌ID")
    user_id: Mapped[int] = mapped_column(UnsignedInt, ForeignKey(User.id), nullable=False, comment="用户ID")
    token: Mapped[str] = mapped_column(String(255), nullable=False, comment="令牌的 sha256 摘要")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<UserToken(id={self.id}, user_id={self.user_id})>"
