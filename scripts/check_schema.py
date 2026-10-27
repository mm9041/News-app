"""检查 ORM 模型与数据库实际结构是否一致。

项目靠手工执行 database.sql 建表，没有 Alembic。一旦改了模型忘了同步 SQL
（或反过来），只有运行时才会以 `1054 Unknown column` / `1146 Table doesn't exist`
的形式暴露出来，而且往往是在某个不常用的分支上。

这个脚本把差异提前打出来：列、索引/唯一约束、unsigned 标记、多余的表。

用法：
    python scripts/check_schema.py

退出码：0 = 一致；1 = 有差异。
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

load_dotenv(BASE_DIR / ".env", override=False)

# 必须把所有模型都导入进来，Base.metadata 才知道有哪些表
from models import ai_chat, ai_conversation, comment, favorite, follow, history, like, news, notification, source, tag, users  # noqa: F401
from models.base import Base


def build_url() -> str:
    return (
        f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', '')}"
        f"@{os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '3306')}"
        f"/{os.getenv('DB_NAME', 'news_app')}?charset=utf8mb4"
    )


def main() -> int:
    engine = create_engine(build_url())
    insp = inspect(engine)
    db_tables = set(insp.get_table_names())
    orm_tables = {table.name: table for table in Base.metadata.sorted_tables}

    problems: list[str] = []

    for name, table in orm_tables.items():
        if name not in db_tables:
            problems.append(f"[缺表] {name}：模型有、库没有")
            continue

        db_cols = {col["name"]: col for col in insp.get_columns(name)}
        orm_cols = {col.name: col for col in table.columns}

        for col in orm_cols.keys() - db_cols.keys():
            problems.append(f"[缺列] {name}.{col}：模型有、库没有")
        for col in db_cols.keys() - orm_cols.keys():
            problems.append(f"[多列] {name}.{col}：库有、模型没声明")

        # unsigned 是最容易漂移、也最容易在写入负数时才炸的差异，单独比对。
        # 注意不能用 str(type) 判断：MySQL 反射回来的 `INTEGER(unsigned=True)`
        # 打印出来只是 "INTEGER"，unsigned 信息在属性里。
        for col in orm_cols.keys() & db_cols.keys():
            orm_unsigned = bool(getattr(orm_cols[col].type, "unsigned", False))
            db_unsigned = bool(getattr(db_cols[col]["type"], "unsigned", False))
            if orm_unsigned != db_unsigned:
                flag = lambda v: "UNSIGNED" if v else "有符号"
                problems.append(
                    f"[类型] {name}.{col}：模型 {flag(orm_unsigned)}，库 {flag(db_unsigned)}"
                    f"（{db_cols[col]['type']!r}）"
                )

        db_indexes = {idx["name"] for idx in insp.get_indexes(name) if idx["name"]}
        db_indexes |= {con["name"] for con in insp.get_unique_constraints(name) if con["name"]}
        db_indexes.discard("PRIMARY")

        orm_indexes = {idx.name for idx in table.indexes if idx.name}
        for con in table.constraints:
            if con.__class__.__name__ == "UniqueConstraint" and con.name:
                orm_indexes.add(con.name)

        for idx in orm_indexes - db_indexes:
            problems.append(f"[缺索引] {name}.{idx}：模型有、库没有")
        for idx in db_indexes - orm_indexes:
            problems.append(f"[多索引] {name}.{idx}：库有、模型没声明")

    for name in db_tables - set(orm_tables):
        problems.append(f"[多表] {name}：库里有、模型没声明")

    if problems:
        print(f"发现 {len(problems)} 处差异：")
        for problem in problems:
            print("  " + problem)
        print("\n以 database.sql 为准改库，或反过来同步模型；两边改完重跑本脚本。")
        return 1

    print(f"一致：{len(orm_tables)} 张表，列 / 索引 / unsigned 均与 database.sql 对齐")
    return 0


if __name__ == "__main__":
    sys.exit(main())
