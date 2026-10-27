"""点赞与个性化推荐。"""

import pytest

NEWS_ID = 45


def _auth(user):
    return {"Authorization": user["token"]}


# ---------------------------------------------------------------- 点赞


def test_like_requires_login(client):
    assert client.put(f"/api/news/{NEWS_ID}/like").status_code == 401


def test_like_and_unlike_are_idempotent(client, temp_user):
    headers = _auth(temp_user)
    # 清场：确保起始状态是「没赞过」
    client.delete(f"/api/news/{NEWS_ID}/like", headers=headers)
    base = client.get("/api/news/detail", params={"id": NEWS_ID}, headers=headers).json()["data"]["likes"]

    first = client.put(f"/api/news/{NEWS_ID}/like", headers=headers)
    assert first.status_code == 200
    assert first.json()["data"] == {"liked": True, "likes": base + 1}

    # 重复点赞是幂等的，不会把计数加上去
    second = client.put(f"/api/news/{NEWS_ID}/like", headers=headers)
    assert second.json()["data"]["likes"] == base + 1

    detail = client.get("/api/news/detail", params={"id": NEWS_ID}, headers=headers).json()["data"]
    assert detail["isLiked"] is True
    assert detail["likes"] == base + 1

    result = client.delete(f"/api/news/{NEWS_ID}/like", headers=headers)
    assert result.json()["data"] == {"liked": False, "likes": base}

    # 再取消一次也成功，不会报错
    again = client.delete(f"/api/news/{NEWS_ID}/like", headers=headers)
    assert again.status_code == 200
    assert again.json()["data"]["likes"] == base


def test_guest_detail_has_likes_flag(client):
    resp = client.get("/api/news/detail", params={"id": NEWS_ID})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "likes" in data
    assert data["isLiked"] is False


def test_like_missing_news(client, temp_user):
    resp = client.put("/api/news/999999/like", headers=_auth(temp_user))
    assert resp.status_code == 404


# ---------------------------------------------------------------- 推荐


def test_recommend_for_guest_returns_list(client):
    resp = client.get("/api/news/recommend")
    assert resp.status_code == 200

    items = resp.json()["data"]["list"]
    assert items
    assert len(items) <= 8
    # 与列表接口字段一致，不带正文
    assert "content" not in items[0]
    assert "categoryId" in items[0]


def test_recommend_respects_limit(client, temp_user):
    resp = client.get("/api/news/recommend", params={"limit": 3}, headers=_auth(temp_user))
    assert resp.status_code == 200
    assert len(resp.json()["data"]["list"]) <= 3


def test_recommend_excludes_read_news(client, temp_user):
    """看过的不该再被推荐 —— 兴趣分类和热门补齐两条路径都要排除。"""
    headers = _auth(temp_user)
    client.post("/api/history/add", json={"newsId": NEWS_ID}, headers=headers)

    resp = client.get("/api/news/recommend", params={"limit": 20}, headers=headers)
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["data"]["list"]]
    assert NEWS_ID not in ids


@pytest.mark.parametrize("limit", [0, 21])
def test_recommend_limit_validation(client, limit):
    resp = client.get("/api/news/recommend", params={"limit": limit})
    assert resp.status_code == 422
