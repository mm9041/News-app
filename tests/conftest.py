"""pytest 公共夹具。

⚠️ TestClient 必须用 `with` 包起来。直接 `TestClient(app)` 时每次请求都会新起
一个事件循环：第一个用到连接池的请求正常，第二个会崩在
`AttributeError: 'NoneType' object has no attribute 'send'` / `Event loop is closed`。
"""

import os
import sys
import uuid
from pathlib import Path

import pymysql
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env", override=False)

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def db_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "news_app"),
        charset="utf8mb4",
        autocommit=True,
    )


@pytest.fixture
def db():
    """同步数据库连接，用于直接断言库里的状态。"""
    conn = db_conn()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def temp_user(client):
    """注册一个临时用户，用完删掉（token 随外键 CASCADE 一起删）。

    用户名用 `pytest_a_` 前缀，setup 只清理自己前缀的历史残留 ——
    如果清理 `pytest_%`，会把同时段创建的 other_user 一起删掉，
    导致另一个 fixture 的 token 突然失效。
    """
    username = f"pytest_a_{uuid.uuid4().hex[:8]}"
    password = "Pytest123456"

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `user` WHERE username LIKE 'pytest_a_%'")

    _clear_rate_limit("register")

    resp = client.post("/api/user/register", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    yield {"username": username, "password": password, "token": data["token"], "user_id": data["userInfo"]["id"]}

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `user` WHERE username=%s", (username,))


@pytest.fixture
def other_user(client):
    """第二个普通用户，用于验证「不能删别人的评论」。"""
    username = f"pytest_b_{uuid.uuid4().hex[:8]}"
    password = "Pytest123456"

    _clear_rate_limit("register")
    resp = client.post("/api/user/register", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    yield {"username": username, "password": password, "token": data["token"], "user_id": data["userInfo"]["id"]}

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `user` WHERE username=%s", (username,))


@pytest.fixture
def admin_user(client, temp_user, db):
    """在 temp_user 基础上把 is_admin 置 1，并重新登录换一个带新状态的 token。

    重新登录是必须的：create_token 是「每用户一条」，旧 token 会被覆盖；
    而且登录响应里的 userInfo.isAdmin 来自重新查库，能反映刚才的 UPDATE。
    """
    with db.cursor() as cur:
        cur.execute("UPDATE `user` SET is_admin=1 WHERE id=%s", (temp_user["user_id"],))

    # 每个用例都会登录一次，跑满 10 次就会撞上「登录 10 次/分」的限流，
    # 表现为 fixture 里的 assert 429 失败 —— 所以登录前先清计数
    _clear_rate_limit("login")

    resp = client.post(
        "/api/user/login",
        json={"username": temp_user["username"], "password": temp_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["userInfo"]["isAdmin"] is True

    return {**temp_user, "token": data["token"]}


def _clear_rate_limit(prefix: str) -> None:
    """清掉指定前缀的限流 key。Redis 不可用时静默跳过。"""
    try:
        import redis

        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        keys = list(r.scan_iter(f"rl:{prefix}:*"))
        if keys:
            r.delete(*keys)
        r.close()
    except Exception:
        pass
