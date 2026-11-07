"""事务原子性与降级行为的回归测试。

1. 注册：用户与令牌同一事务 —— 令牌写入失败时不能留下注册了一半的用户；
2. 通知：附属动作失败不影响已落库的评论 / 点赞（否则用户重试会重复评论）；
3. 标签：超过数据库长度上限的标签在请求校验阶段被拒绝。
"""

import uuid

import pytest
from conftest import _clear_rate_limit


def _auth(user):
    return {"Authorization": user["token"]}


def _create_news(client, admin_user, title: str) -> int:
    payload = {"title": title, "content": "正文", "categoryId": 1}
    resp = client.post("/api/admin/news", json=payload, headers=_auth(admin_user))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _cleanup_news(db, news_id: int) -> None:
    """news_like / news_comment / news_tag 的外键没有 CASCADE，删新闻前先清依赖行。"""
    with db.cursor() as cur:
        cur.execute("DELETE FROM news_comment WHERE news_id=%s", (news_id,))
        cur.execute("DELETE FROM news_like WHERE news_id=%s", (news_id,))
        cur.execute("DELETE FROM news_tag WHERE news_id=%s", (news_id,))
        cur.execute("DELETE FROM news WHERE id=%s", (news_id,))


def test_register_rolls_back_user_when_token_fails(client, monkeypatch, db):
    username = f"pytest_tx_{uuid.uuid4().hex[:8]}"
    _clear_rate_limit("register")

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated token failure")

    # 路由是 `from crud.users import create_token`，要 patch 路由模块里的引用
    monkeypatch.setattr("routers.users.create_token", _boom)

    # TestClient 默认 raise_server_exceptions=True，会把路由异常原样抛出；
    # 生产环境由 general_exception_handler 转成 500。这里关心的是回滚，不是响应码。
    with pytest.raises(RuntimeError, match="simulated token failure"):
        client.post("/api/user/register", json={"username": username, "password": "Pytest123456"})

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM `user` WHERE username=%s", (username,))
        assert cur.fetchone()[0] == 0, "令牌失败时用户必须一起回滚"


def test_admin_rejects_too_long_tag(client, admin_user):
    payload = {
        "title": "pytest 标签长度校验",
        "content": "正文",
        "categoryId": 1,
        "tags": ["标" * 31],
    }
    resp = client.post("/api/admin/news", json=payload, headers=_auth(admin_user))
    assert resp.status_code == 422, resp.text
    # 校验错误必须指向 tags 字段，而不是笼统的 500
    assert "tags" in str(resp.json())


def test_admin_accepts_tag_at_length_limit(client, admin_user, db):
    """30 字符正好是 tag.name 的上限，不能被误拦。"""
    tag = "标" * 30
    payload = {
        "title": f"pytest 标签上限 {uuid.uuid4().hex[:6]}",
        "content": "正文",
        "categoryId": 1,
        "tags": [tag],
    }
    resp = client.post("/api/admin/news", json=payload, headers=_auth(admin_user))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["tags"] == [tag]

    news_id = resp.json()["data"]["id"]
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tag WHERE name=%s", (tag,))
            assert cur.fetchone()[0] == 1
    finally:
        _cleanup_news(db, news_id)
        with db.cursor() as cur:
            cur.execute("DELETE FROM tag WHERE name=%s", (tag,))


def test_comment_survives_notification_failure(client, admin_user, temp_user, db, monkeypatch):
    """通知失败不能把「评论成功」变成 500，否则用户重试会发出重复评论。"""
    news_id = _create_news(client, admin_user, f"pytest 通知降级 {uuid.uuid4().hex[:6]}")

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated notification failure")

    monkeypatch.setattr("crud.notification.create", _boom)

    try:
        resp = client.post(
            "/api/comment",
            json={"newsId": news_id, "content": "通知失败也不影响评论"},
            headers=_auth(temp_user),
        )
        assert resp.status_code == 200, resp.text

        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news_comment WHERE news_id=%s", (news_id,))
            assert cur.fetchone()[0] == 1
    finally:
        _cleanup_news(db, news_id)


def test_like_survives_notification_failure(client, admin_user, temp_user, db, monkeypatch):
    news_id = _create_news(client, admin_user, f"pytest 点赞降级 {uuid.uuid4().hex[:6]}")

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated notification failure")

    monkeypatch.setattr("crud.notification.create", _boom)

    try:
        resp = client.put(f"/api/news/{news_id}/like", headers=_auth(temp_user))
        assert resp.status_code == 200, resp.text

        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news_like WHERE news_id=%s", (news_id,))
            assert cur.fetchone()[0] == 1
    finally:
        _cleanup_news(db, news_id)
