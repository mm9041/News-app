"""认证相关：token 只存哈希、明文可用于鉴权、未登录/错误凭证的行为。"""

import pytest
from pydantic import ValidationError

from crud.users import hash_token
from schemas.users import UserRegisterRequest, UserRequest


def test_register_schema_rejects_weak_credentials():
    """注册的强度约束必须在 schema 层挡住，别走到 bcrypt 才炸成 500。"""
    with pytest.raises(ValidationError):
        UserRegisterRequest(username="ab", password="123456")  # 用户名太短

    with pytest.raises(ValidationError):
        UserRegisterRequest(username="abc", password="")  # 空密码

    with pytest.raises(ValidationError):
        # 51 字符：原来没有 max_length，会撞 VARCHAR(50) 变成 500
        UserRegisterRequest(username="a" * 51, password="123456")

    with pytest.raises(ValidationError):
        # 30 个汉字 = 90 字节，字符长度合法但超过 bcrypt 的 72 字节
        UserRegisterRequest(username="abc", password="密" * 30)


def test_login_schema_keeps_legacy_short_password():
    """登录不能套用注册的强度规则：种子账号 admin/admin 只有 5 位。"""
    data = UserRequest(username="admin", password="admin")
    assert data.password == "admin"

    # 超长密码在 schema 拦下（否则 bcrypt 抛 ValueError → 500）
    with pytest.raises(ValidationError):
        UserRequest(username="admin", password="a" * 73)


def test_hash_token_is_sha256_hex():
    digest = hash_token("some-token")
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)
    assert digest == hash_token("some-token")
    assert digest != "some-token"


def test_register_stores_hash_not_plaintext(client, temp_user, db):
    token = temp_user["token"]

    # 明文 token 能正常鉴权
    resp = client.get("/api/user/info", headers={"Authorization": token})
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == temp_user["username"]

    # 库里存的是它的 sha256，不是明文
    with db.cursor() as cur:
        cur.execute("SELECT token FROM user_token WHERE user_id=%s", (temp_user["user_id"],))
        stored = cur.fetchone()[0]

    assert stored == hash_token(token)
    assert stored != token


def test_bearer_prefix_also_works(client, temp_user):
    resp = client.get(
        "/api/user/info",
        headers={"Authorization": f"Bearer {temp_user['token']}"},
    )
    assert resp.status_code == 200


def test_login_sets_httponly_cookie_and_logout_clears_it(client, temp_user):
    """浏览器通道：token 走 httpOnly cookie，登出要连库里的记录一起删。"""
    client.cookies.clear()

    resp = client.post(
        "/api/user/login",
        json={"username": temp_user["username"], "password": temp_user["password"]},
    )
    assert resp.status_code == 200

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie, "必须 httpOnly，否则 XSS 能直接读走"
    assert "samesite=lax" in set_cookie

    # 不带 Authorization 头，只靠 cookie
    info = client.get("/api/user/info")
    assert info.status_code == 200
    assert info.json()["data"]["username"] == temp_user["username"]

    assert client.post("/api/user/logout").status_code == 200
    assert client.get("/api/user/info").status_code == 401, "登出后旧 cookie 必须失效"


def test_invalid_token_is_rejected(client):
    resp = client.get("/api/user/info", headers={"Authorization": "not-a-real-token"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 401


def test_duplicate_username_is_rejected(client, temp_user):
    resp = client.post(
        "/api/user/register",
        json={"username": temp_user["username"], "password": "Another123456"},
    )
    assert resp.status_code == 400
    assert "已存在" in resp.json()["message"]


def test_update_profile_accepts_null_fields(client, temp_user):
    """v2 里 `field: str = None` 会让显式传 null 直接 422，这里盯住回归。"""
    resp = client.put(
        "/api/user/update",
        json={"nickname": None, "bio": "pytest 简介"},
        headers={"Authorization": temp_user["token"]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["bio"] == "pytest 简介"
