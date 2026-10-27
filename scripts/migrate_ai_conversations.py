"""给历史的 AI 聊天记录补会话。

早期 `ai_chat` 没有会话概念，一行就是一轮问答。这个脚本按
「同一用户、相邻两条间隔 < 30 分钟」把它们归到同一个会话里，
标题取该会话第一条用户消息的前 30 个字。

可重复执行：只处理 `conversation_id IS NULL` 的行。

用法：python scripts/migrate_ai_conversations.py
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pymysql
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env", override=False)

GAP = timedelta(minutes=30)
TITLE_LEN = 30


def main() -> int:
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "news_app"),
        charset="utf8mb4",
        autocommit=True,
    )

    created = 0
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, message, created_at FROM ai_chat "
            "WHERE conversation_id IS NULL ORDER BY user_id, created_at, id"
        )
        rows = cur.fetchall()

        current_user = None
        last_time = None
        conv_id = None

        for chat_id, user_id, message, created_at in rows:
            need_new = (
                user_id != current_user
                or last_time is None
                or (created_at - last_time) > GAP
            )
            if need_new:
                title = (message or "").strip().replace("\n", " ")[:TITLE_LEN] or "历史对话"
                cur.execute(
                    "INSERT INTO ai_conversation (user_id, title, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (user_id, title, created_at, created_at),
                )
                conv_id = cur.lastrowid
                current_user = user_id
                created += 1

            cur.execute(
                "UPDATE ai_chat SET conversation_id=%s WHERE id=%s", (conv_id, chat_id)
            )
            last_time = created_at

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ai_conversation")
        total_conv = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ai_chat WHERE conversation_id IS NULL")
        orphan = cur.fetchone()[0]

    conn.close()
    print(f"迁移完成：新建 {created} 个会话，现有会话 {total_conv} 个，未归属消息 {orphan} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
