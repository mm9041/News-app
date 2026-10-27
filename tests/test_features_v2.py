"""评论回复、标签、数据看板。

这三块的 fixture 都挂在「管理员发一条带标签的新闻」上，
用例结束删新闻，评论/标签关联随外键 CASCADE 一起清掉。
"""

import pytest


def _auth(user):
    return {"Authorization": user["token"]}


@pytest.fixture
def news_with_tags(client, admin_user):
    resp = client.post(
        "/api/admin/news",
        json={
            "title": "标签与回复测试新闻",
            "content": "正文。",
            "categoryId": 1,
            "tags": ["pytest标签", "AI", "AI"],  # 故意重复，后端要去重
        },
        headers=_auth(admin_user),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    news_id = data["id"]

    yield {"id": news_id, "tags": data.get("tags", []), "admin": admin_user}

    client.delete(f"/api/admin/news/{news_id}", headers=_auth(admin_user))


# ---------------------------------------------------------------- 评论回复


def test_reply_nests_under_parent(client, news_with_tags, other_user, temp_user):
    news_id = news_with_tags["id"]

    root = client.post(
        "/api/comment/add", json={"newsId": news_id, "content": "一级评论"}, headers=_auth(other_user)
    ).json()["data"]["id"]

    reply = client.post(
        "/api/comment/add",
        json={"newsId": news_id, "content": "我来回复", "parentId": root},
        headers=_auth(temp_user),
    )
    assert reply.status_code == 200, reply.text

    data = client.get("/api/comment/list", params={"newsId": news_id}, headers=_auth(other_user)).json()["data"]
    item = next(i for i in data["list"] if i["id"] == root)

    assert len(item["replies"]) == 1
    nested = item["replies"][0]
    assert nested["content"] == "我来回复"
    assert nested["parentId"] == root
    # 被回复人是一级评论的作者
    assert nested["replyTo"] == (other_user["username"])


def test_reply_notifies_replied_user(client, news_with_tags, other_user, temp_user):
    news_id = news_with_tags["id"]
    root = client.post(
        "/api/comment/add", json={"newsId": news_id, "content": "求回复"}, headers=_auth(other_user)
    ).json()["data"]["id"]

    client.post(
        "/api/comment/add",
        json={"newsId": news_id, "content": "回你了", "parentId": root},
        headers=_auth(temp_user),
    )

    data = client.get("/api/notification/list", headers=_auth(other_user)).json()["data"]
    assert any(i["type"] == "reply" and i["newsId"] == news_id for i in data["list"])


def test_reply_to_reply_stays_two_levels(client, news_with_tags, other_user, temp_user):
    """回复一条回复时，仍然挂在同一个一级评论下，不会出现第三层。"""
    news_id = news_with_tags["id"]
    root = client.post(
        "/api/comment/add", json={"newsId": news_id, "content": "根"}, headers=_auth(other_user)
    ).json()["data"]["id"]
    first_reply = client.post(
        "/api/comment/add",
        json={"newsId": news_id, "content": "回复1", "parentId": root},
        headers=_auth(temp_user),
    ).json()["data"]["id"]

    client.post(
        "/api/comment/add",
        json={"newsId": news_id, "content": "回复2", "parentId": first_reply},
        headers=_auth(other_user),
    )

    data = client.get("/api/comment/list", params={"newsId": news_id}, headers=_auth(other_user)).json()["data"]
    item = next(i for i in data["list"] if i["id"] == root)
    # 两条回复都平铺在同一层
    assert len(item["replies"]) == 2
    assert all(r["parentId"] == root for r in item["replies"])


def test_reply_to_missing_comment(client, news_with_tags, temp_user):
    resp = client.post(
        "/api/comment/add",
        json={"newsId": news_with_tags["id"], "content": "x", "parentId": 999999},
        headers=_auth(temp_user),
    )
    assert resp.status_code == 404


def test_delete_root_cascades_replies(client, news_with_tags, other_user, temp_user):
    news_id = news_with_tags["id"]
    root = client.post(
        "/api/comment/add", json={"newsId": news_id, "content": "将被删"}, headers=_auth(other_user)
    ).json()["data"]["id"]
    client.post(
        "/api/comment/add",
        json={"newsId": news_id, "content": "回复也会没", "parentId": root},
        headers=_auth(temp_user),
    )

    client.delete(f"/api/comment/{root}", headers=_auth(other_user))

    data = client.get("/api/comment/list", params={"newsId": news_id}).json()["data"]
    assert all(i["id"] != root for i in data["list"])


# ---------------------------------------------------------------- 标签


def test_news_keeps_deduped_tags(client, news_with_tags):
    # 传了 ["pytest标签", "AI", "AI"]，去重后两个
    assert sorted(news_with_tags["tags"]) == sorted(["pytest标签", "AI"])


def test_detail_returns_tags_with_id(client, news_with_tags):
    detail = client.get("/api/news/detail", params={"id": news_with_tags["id"]}).json()["data"]
    assert {t["name"] for t in detail["tags"]} == {"pytest标签", "AI"}
    assert all("id" in t for t in detail["tags"])


def test_list_news_by_tag(client, news_with_tags):
    detail = client.get("/api/news/detail", params={"id": news_with_tags["id"]}).json()["data"]
    tag_id = next(t["id"] for t in detail["tags"] if t["name"] == "pytest标签")

    data = client.get(f"/api/tag/{tag_id}/news").json()["data"]
    assert any(i["id"] == news_with_tags["id"] for i in data["list"])
    assert data["tag"]["name"] == "pytest标签"


def test_hot_tags_contains_new_tag(client, news_with_tags):
    data = client.get("/api/tag/hot", params={"limit": 50}).json()["data"]
    names = [t["name"] for t in data]
    assert "pytest标签" in names


def test_update_news_replaces_tags(client, news_with_tags):
    news_id = news_with_tags["id"]
    resp = client.put(
        f"/api/admin/news/{news_id}",
        json={
            "title": "标签与回复测试新闻",
            "content": "正文。",
            "categoryId": 1,
            "tags": ["新标签"],
        },
        headers=_auth(news_with_tags["admin"]),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["tags"] == ["新标签"]

    detail = client.get("/api/news/detail", params={"id": news_id}).json()["data"]
    assert [t["name"] for t in detail["tags"]] == ["新标签"]


# ---------------------------------------------------------------- 看板


def test_stats_require_admin(client, temp_user):
    assert client.get("/api/admin/stats", headers=_auth(temp_user)).status_code == 403


def test_stats_shape(client, admin_user):
    resp = client.get("/api/admin/stats", params={"days": 7}, headers=_auth(admin_user))
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert set(data) == {"overview", "trend", "categories", "topNews"}
    assert set(data["overview"]) == {"news", "comments", "users", "views"}
    assert len(data["trend"]) == 7
    assert data["overview"]["news"] > 0
    assert data["categories"]
