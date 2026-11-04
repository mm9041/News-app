from datetime import datetime

from sqlalchemy.dialects.mysql import INTEGER, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# database.sql 里所有主键/外键以及 news.views 都是 `INT UNSIGNED`。
# ORM 若统一写 Integer（= 有符号 INT），模型与建表 SQL 就对不上，
# scripts/check_schema.py 会把它当成漂移报出来。
# 项目只跑 MySQL，直接用 MySQL 方言的整型即可。
UnsignedInt = INTEGER(unsigned=True)


class Base(DeclarativeBase):
    """全项目唯一的 DeclarativeBase。

    所有 ORM 模型都继承它，好处是共享同一个 metadata：
    跨表外键、create_all()、Alembic 迁移都能看到完整表结构。
    这里刻意不放任何列 —— 有列的话会被所有子类继承，
    而 user_token / favorite / history 等表并没有那些列。
    """
    pass


class TimestampMixin:
    """created_at / updated_at 时间戳混入。

    只有数据库里确实存在这两列的表才能继承它（news、news_category）。
    user_token / favorite / history / ai_chat 表没有 updated_at
    列，继承会导致查询报 1054 Unknown column。

    注意 default / onupdate 必须传**可调用对象**（这里是 datetime.now，不带括号）。
    写成 default=datetime.now() 会在模块导入时求值，冻结成固定时间戳（不报错但数据全错）。
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=datetime.now,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )
