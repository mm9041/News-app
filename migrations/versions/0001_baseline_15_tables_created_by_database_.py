"""baseline: 15 tables created by database.sql

基线迁移，**故意是空的**：现有 15 张表由 database.sql 一次建好，
Alembic 从这里开始只记录增量。

- 新环境：先 `mysql < database.sql`，再 `alembic stamp 0001`
- 已有环境：直接 `alembic stamp 0001`
- 之后改表：`alembic revision --autogenerate -m "说明"` → `alembic upgrade head`

Revision ID: 0001
Revises:
Create Date: 2026-11-04 19:13:59.672512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空迁移：基线已由 database.sql 建好。"""
    pass


def downgrade() -> None:
    """基线没有可回滚的 DDL。"""
    pass
