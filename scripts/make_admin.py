"""把某个用户设为管理员（或取消）。

用法：
    python scripts/make_admin.py <username>            # 设为管理员
    python scripts/make_admin.py <username> --revoke   # 取消管理员

改完让该用户重新登录一次：`/api/user/info` 会重新返回 `isAdmin`，
前端据此显示「管理后台」入口。真正的权限校验在后端 `get_current_admin`。
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pymysql
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env", override=False)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    username = sys.argv[1]
    is_admin = "--revoke" not in sys.argv[2:]

    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "news_app"),
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE `user` SET is_admin=%s WHERE username=%s", (1 if is_admin else 0, username))
            if cur.rowcount == 0:
                cur.execute("SELECT COUNT(*) FROM `user` WHERE username=%s", (username,))
                if cur.fetchone()[0] == 0:
                    print(f"用户不存在：{username}")
                    return 1
    finally:
        conn.close()

    action = "设为管理员" if is_admin else "取消管理员"
    print(f"已把 {username} {action}，请让该用户重新登录以刷新前端状态")
    return 0


if __name__ == "__main__":
    sys.exit(main())
