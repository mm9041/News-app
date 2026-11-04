"""Alembic 迁移环境。

项目现状：**新装库仍然走 `database.sql`**（一次建好 15 张表 + 种子数据），
Alembic 只负责之后的**增量变更**。首次接入的做法是：

    alembic stamp 0001        # 把现有库标记到 baseline，不执行任何 DDL

之后每次改模型：

    alembic revision --autogenerate -m "说明"
    alembic upgrade head

`database.sql` 与模型的一致性仍由 `scripts/check_schema.py` 兜底。
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.db_conf import ASYNC_DATABASE_URL  # noqa: E402

# 必须把所有模型都导入进来，Base.metadata 才知道有哪些表。
# 漏一个模块的表现是 autogenerate 想「删除」那张表。
from models import (  # noqa: E402,F401
    ai_chat,
    ai_conversation,
    comment,
    favorite,
    follow,
    history,
    like,
    news,
    notification,
    source,
    tag,
    users,
)
from models.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 连接串只从 .env 取（config/db_conf.py 已经 load_dotenv），
# 不在 alembic.ini 里再写一份，避免两处不一致。
# ⚠️ 密码里若有 % 会被 configparser 当插值符，必须先转义。
config.set_main_option("sqlalchemy.url", ASYNC_DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata

# Alembic 自己的版本表既不属于业务模型，也不该被 check_schema 当成"多表"。
ALEMBIC_VERSION_TABLE = "alembic_version"


def include_object(object_, name, type_, reflected, compare_to):
    """autogenerate 的对象过滤。

    外键在库里是显式命名的（`fk_news_category` 这种），而模型里是匿名的
    `ForeignKey("news_category.id")`。Alembic 按名字比对，于是每一轮都会报
    「remove fk + add fk」—— 这些 DDL 没有任何实际效果，纯噪声。

    所以这里跳过全部外键约束的比较。**代价**：以后真要改外键（改级联、换指向），
    autogenerate 不会提醒，得手写 `op.drop_constraint` / `op.create_foreign_key`。
    """
    if type_ == "foreign_key_constraint":
        return False
    if type_ == "table" and name == ALEMBIC_VERSION_TABLE:
        return False
    return True


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连库（alembic upgrade head --sql）。"""
    context.configure(
        url=ASYNC_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # 只比较列类型。不比较 server_default：本项目的默认值都在模型/建表 SQL 里，
        # 交给 MySQL 处理，硬比会生成一堆无意义的 DDL。
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
