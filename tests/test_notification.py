"""消息通知：评论/点赞触发、自己操作不通知、已读与未读数。"""

import pytest


def _auth(user):
    return {"Authorization": user["token"]}


@pytest.fixture
def published_news(client, admin_user):
    """由 admin 发布一条新闻（带发布者 user_id），测试结束删掉。

    删除新闻时，评论和通知都会随外键 CASCADE 一起清掉。
    """
    resp = client.post(
        "/api/admin/news",
        json={
            "title": "通知测试新闻",
            "content": "用于验证通知逻辑。",
            "categoryId": 1,
        },
        headers=_auth(admin_user),
    )
    assert resp.status_code == 201, resp.text
    news_id = resp.json()["data"]["id"]

    yield {"news_id": news_id, "admin": admin_user}

    client.delete(f"/api/admin/news/{news_id}", headers=_auth(admin_user))


def test_notification_requires_login(client):
    assert client.get("/api/notification").status_code == 401
    assert client.get("/api/notification/unread-count").status_code == 401


def test_comment_triggers_notification(client, published_news, other_user):
    news_id = published_news["news_id"]

    resp = client.post(
        "/api/comment",
        json={"newsId": news_id, "content": "写得好"},
        headers=_auth(other_user),
    )
    assert resp.status_code == 201

    data = client.get("/api/notification", headers=_auth(published_news["admin"])).json()["data"]
    assert data["unread"] >= 1

    item = next(i for i in data["list"] if i["newsId"] == news_id)
    assert item["type"] == "comment"
    assert item["actor"]["id"] == other_user["user_id"]
    assert item["commentPreview"] == "写得好"
    assert item["isRead"] is False


def test_like_triggers_notification_once(client, published_news, other_user):
    news_id = published_news["news_id"]
    admin = published_news["admin"]

    client.put(f"/api/news/{news_id}/like", headers=_auth(other_user))
    first = client.get("/api/notification/unread-count", headers=_auth(admin)).json()["data"]["count"]
    assert first == 1

    # 重复点赞（幂等）不该再发一条
    client.put(f"/api/news/{news_id}/like", headers=_auth(other_user))
    second = client.get("/api/notification/unread-count", headers=_auth(admin)).json()["data"]["count"]
    assert second == 1

    items = client.get("/api/notification", headers=_auth(admin)).json()["data"]["list"]
    assert any(i["type"] == "like" and i["newsId"] == news_id for i in items)


def test_self_interaction_sends_nothing(client, published_news):
    """自己评论/点赞自己的新闻不该给自己发通知。"""
    news_id = published_news["news_id"]
    admin = published_news["admin"]

    client.post("/api/comment", json={"newsId": news_id, "content": "自己评"}, headers=_auth(admin))
    client.put(f"/api/news/{news_id}/like", headers=_auth(admin))

    count = client.get("/api/notification/unread-count", headers=_auth(admin)).json()["data"]["count"]
    assert count == 0


def test_mark_read_and_mark_all(client, published_news, other_user):
    news_id = published_news["news_id"]
    admin = published_news["admin"]

    client.post("/api/comment", json={"newsId": news_id, "content": "第一条"}, headers=_auth(other_user))
    client.post("/api/comment", json={"newsId": news_id, "content": "第二条"}, headers=_auth(other_user))

    data = client.get("/api/notification", headers=_auth(admin)).json()["data"]
    assert data["unread"] == 2

    # 单条已读
    target = data["list"][0]["id"]
    resp = client.patch(f"/api/notification/{target}", json={"isRead": True}, headers=_auth(admin))
    assert resp.status_code == 200

    assert client.get("/api/notification/unread-count", headers=_auth(admin)).json()["data"]["count"] == 1

    # 全部已读
    client.patch("/api/notification", json={"isRead": True}, headers=_auth(admin))
    assert client.get("/api/notification/unread-count", headers=_auth(admin)).json()["data"]["count"] == 0


def test_cannot_mark_others_notification(client, published_news, other_user):
    news_id = published_news["news_id"]
    admin = published_news["admin"]

    client.post("/api/comment", json={"newsId": news_id, "content": "给我的"}, headers=_auth(other_user))
    target = client.get("/api/notification", headers=_auth(admin)).json()["data"]["list"][0]["id"]

    # other_user 去标记 admin 的通知：条件里带 user_id，应该一条都命中不了
    resp = client.patch(f"/api/notification/{target}", json={"isRead": True}, headers=_auth(other_user))
    assert resp.json()["data"]["updated"] == 0

    # admin 那边仍然是未读
    assert client.get("/api/notification/unread-count", headers=_auth(admin)).json()["data"]["count"] == 1
