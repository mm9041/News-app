"""搜索与管理后台。

依赖 db 的用例自己创建、自己删除，不依赖 database.sql 里的示例新闻。
"""

import uuid

import pytest

LIST_ITEM_FIELDS = {
    "id", "title", "description", "image",
    "author", "categoryId", "views", "publishTime",
}

MARK = "唯一探针标记"


def _payload(title: str, category_id: int = 1) -> dict:
    return {
        "title": title,
        "description": "测试摘要",
        "content": f"第一段。\n\n第二段：{MARK}。",
        "author": "pytest",
        "categoryId": category_id,
        "image": "https://picsum.photos/seed/pytest/200/200",
    }


@pytest.fixture
def created_news(client, admin_user):
    """创建一条新闻，用例结束后无论如何都删掉（news 没有用户外键，不会自动清理）。"""
    title = f"pytest 测试新闻 {uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/admin/news",
        json=_payload(title),
        headers={"Authorization": admin_user["token"]},
    )
    assert resp.status_code == 200, resp.text
    news_id = resp.json()["data"]["id"]

    yield {"id": news_id, "title": title, "token": admin_user["token"]}

    client.delete(f"/api/admin/news/{news_id}", headers={"Authorization": admin_user["token"]})


# ---------------------------------------------------------------- 搜索


def test_search_finds_newly_created_news(client, created_news):
    resp = client.get("/api/news/search", params={"keyword": "探针"})
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert any(item["id"] == created_news["id"] for item in data["list"])
    # 搜索结果与列表接口字段一致，不能带正文
    assert set(data["list"][0]) == LIST_ITEM_FIELDS
    assert "content" not in data["list"][0]


def test_search_does_not_return_irrelevant_news(client):
    """ngram 自然语言模式会把长词切成片段、任意片段命中就算一条；
    改成布尔短语后这个查询必须是 0 条。"""
    resp = client.get("/api/news/search", params={"keyword": "绝对不存在的词zzz"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 0


def test_search_single_char_falls_back_to_like(client, created_news):
    """ngram_token_size=2，单字 MATCH 必然 0 条，必须靠 LIKE 兜底。"""
    resp = client.get("/api/news/search", params={"keyword": "探"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] > 0


def test_search_escapes_like_wildcards(client):
    """用户输入 % 不应该变成通配符把所有新闻都搜出来。"""
    resp = client.get("/api/news/search", params={"keyword": "%%%"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 0


@pytest.mark.parametrize("params", [{}, {"keyword": ""}])
def test_search_requires_keyword(client, params):
    resp = client.get("/api/news/search", params=params)
    assert resp.status_code == 422
    assert resp.json()["code"] == 422


# ---------------------------------------------------------------- 权限


def test_admin_requires_login(client):
    resp = client.get("/api/admin/news")
    assert resp.status_code == 401


def test_admin_forbidden_for_normal_user(client, temp_user):
    resp = client.get("/api/admin/news", headers={"Authorization": temp_user["token"]})
    assert resp.status_code == 403
    assert "管理员" in resp.json()["message"]


# ---------------------------------------------------------------- CRUD


def test_admin_list_returns_content(client, admin_user):
    resp = client.get("/api/admin/news", params={"pageSize": 1}, headers={"Authorization": admin_user["token"]})
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["list"]
    # 管理端编辑要回填正文，和前台列表不同
    assert "content" in data["list"][0]
    assert "categoryId" in data["list"][0]


def test_created_news_appears_in_public_list(client, created_news):
    """写操作必须让列表缓存失效，否则最多 30 分钟看不到。"""
    resp = client.get("/api/news/list", params={"categoryId": 1, "pageSize": 10})
    ids = [item["id"] for item in resp.json()["data"]["list"]]
    assert created_news["id"] in ids


def test_admin_update_and_delete(client, admin_user, created_news):
    token = {"Authorization": admin_user["token"]}
    news_id = created_news["id"]

    resp = client.put(
        f"/api/admin/news/{news_id}",
        json=_payload("pytest 改名后的标题"),
        headers=token,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "pytest 改名后的标题"

    resp = client.delete(f"/api/admin/news/{news_id}", headers=token)
    assert resp.status_code == 200

    resp = client.get(f"/api/admin/news/{news_id}", headers=token)
    assert resp.status_code == 404


def test_admin_rejects_invalid_payload(client, admin_user):
    resp = client.post(
        "/api/admin/news",
        json={"title": "", "content": "x", "categoryId": 1},
        headers={"Authorization": admin_user["token"]},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == 422
