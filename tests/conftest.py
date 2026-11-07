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


@pytest.fixture(autouse=True)
def _isolate_cookies(client):
    """每个用例前后清空 cookie jar。

    注册 / 登录接口现在会下发 httpOnly cookie，而 client 是 session 级的：
    不清的话，上一个用例注册出来的登录态会漏到下一个用例，
    "游客"其实带着有效 cookie（表现为 test_guest_can_read_but_not_delete 失败）。

    用例之间统一用 Authorization 头鉴权；cookie 只在 test_auth 里专门验证。
    """
    client.cookies.clear()
    yield
    client.cookies.clear()


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
            # 用转义后的下划线精确匹配前缀：LIKE 'pytest_a_%' 里的 _ 是通配符，
            # 会把 pytest_adm_xxx 也一起删掉
            cur.execute(r"DELETE FROM `user` WHERE username LIKE 'pytest\_a\_%'")

    _clear_rate_limit("register")

    resp = client.post("/api/user/register", json={"username": username, "password": password})
    assert resp.status_code == 201, resp.text
    assert resp.headers["Location"] == "/api/user/me"
    payload = resp.json()
    assert payload["code"] == 201
    data = payload["data"]

    # 注册/登录会下发 cookie；夹具建好用户后清掉，避免把登录态漏给"游客"用例
    client.cookies.clear()
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
    assert resp.status_code == 201, resp.text
    assert resp.headers["Location"] == "/api/user/me"
    payload = resp.json()
    assert payload["code"] == 201
    data = payload["data"]

    # 注册/登录会下发 cookie；夹具建好用户后清掉，避免把登录态漏给"游客"用例
    client.cookies.clear()
    yield {"username": username, "password": password, "token": data["token"], "user_id": data["userInfo"]["id"]}

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM `user` WHERE username=%s", (username,))


@pytest.fixture
def admin_user(client, db):
    """独立的管理员账号。

    ⚠️ 不能基于 temp_user：`create_token` 是「每用户只保留一条」，
    admin_user 重新登录会把 temp_user 的 token 顶掉，
    同一个用例里再用 temp_user 的 token 就是 401。
    """
    username = f"pytest_adm_{uuid.uuid4().hex[:8]}"
    password = "Pytest123456"

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(r"DELETE FROM `user` WHERE username LIKE 'pytest\_adm\_%'")

    _clear_rate_limit("register")
    resp = client.post("/api/user/register", json={"username": username, "password": password})
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["data"]["userInfo"]["id"]

    with db.cursor() as cur:
        cur.execute("UPDATE `user` SET is_admin=1 WHERE id=%s", (user_id,))

    # 每个用例都会登录一次，跑满 10 次就会撞上「登录 10 次/分」的限流
    _clear_rate_limit("login")

    resp = client.post(
        "/api/user/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["userInfo"]["isAdmin"] is True

    # 注册/登录会下发 cookie；夹具建好用户后清掉，避免把登录态漏给"游客"用例
    client.cookies.clear()
    yield {
        "username": username,
        "password": password,
        "user_id": user_id,
        "token": data["token"],
    }

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
        # 滑动窗口限流的 key 是 `rl:{prefix}`（不带 bucket 后缀）；
        # 兼容旧固定窗口的 `rl:{prefix}:{bucket}`，两个模式都清
        keys = list(r.scan_iter(f"rl:{prefix}:*")) + list(r.scan_iter(f"rl:{prefix}"))
        if keys:
            r.delete(*keys)
        r.close()
    except Exception:
        pass
