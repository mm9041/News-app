"""drop redundant fk_history_user_idx on history

`fk_history_user_idx (user_id)` 是另外两个索引的左前缀：

    user_news_unique (user_id, news_id)
    idx_user_view    (user_id, view_time, id)

B+ 树按第一列排序，所以「只查 user_id」本来就走得到上面两个，EXPLAIN 也证实
优化器从没选过这条单列索引（只有 COUNT(*) 会用它做 covering scan，而
user_news_unique 同样是 covering，只是每行多 4 字节）。

外键也不依赖它：InnoDB 只要求外键列上有可用索引，左前缀满足。
删掉后 history 的写入少维护一棵 B+ 树 —— 这张表每次浏览新闻都要 upsert。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04 19:59:46.949811

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("fk_history_user_idx", table_name="history")


def downgrade() -> None:
    op.create_index("fk_history_user_idx", "history", ["user_id"], unique=False)
