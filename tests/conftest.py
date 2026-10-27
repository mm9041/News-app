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

    同时清掉注册接口的限流计数 —— 反复跑测试很容易在同一分钟内超过 5 次。
    """
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    password = "Pytest123456"

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `user` WHERE username LIKE 'pytest_%'")

    _clear_rate_limit("register")

    resp = client.post("/api/user/register", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    yield {"username": username, "password": password, "token": data["token"], "user_id": data["userInfo"]["id"]}

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `user` WHERE username=%s", (username,))


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
