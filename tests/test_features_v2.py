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


# ---------------------------------------------------------------- 作者关注


def test_follow_author_and_list(client, temp_user, db):
    """关注作者 → 列表可见 → total 是全量计数（不是本页长度）→ 取关。

    这条用例原来写的是 `total >= 40`，本意是「total 必须是全量计数、不能等于本页条数」，
    但用一个魔数表达这个意图，种子数据一缩水就误报（库里只剩 12 条 → 假失败）。
    改成从库里现算期望值，再翻完所有页比对，既与原意一致，也不再依赖数据规模。
    """
    author = "海南日报"
    headers = _auth(temp_user)

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM news WHERE author=%s", (author,))
        expected = cur.fetchone()[0]
    assert expected > 0, "种子数据里没有该作者的新闻，用例前提不成立"

    try:
        resp = client.post("/api/follow", params={"name": author}, headers=headers)
        assert resp.status_code == 200

        authors = client.get("/api/follow/authors", headers=headers).json()["data"]
        assert any(
            a["name"] == author and a["newsCount"] == expected for a in authors
        ), "关注列表里的新闻数应与库内一致"

        # 用固定的小页长翻完全部页：既验证 total 是全量计数，
        # 也验证分页不重不漏（这两点是原断言真正想守的东西）。
        page_size = 5
        seen: list[int] = []
        page = 1
        while True:
            data = client.get(
                "/api/follow/news",
                params={"name": author, "page": page, "pageSize": page_size},
                headers=headers,
            ).json()["data"]
            assert data["author"] == author
            assert data["total"] == expected, f"第 {page} 页的 total 与库内条数不一致"
            seen.extend(item["id"] for item in data["list"])
            if not data["hasMore"]:
                break
            page += 1
            assert page <= expected // page_size + 2, "hasMore 一直为 True，疑似死循环"

        assert len(seen) == expected, "翻页拿到的条数与 total 不一致"
        assert len(set(seen)) == expected, "翻页出现重复条目"

        status_data = client.get(
            "/api/follow/status", params={"name": author}, headers=headers
        ).json()["data"]
        assert status_data["following"] is True

        # 幂等：重复关注不产生重复条目
        client.post("/api/follow", params={"name": author}, headers=headers)
        authors_again = client.get("/api/follow/authors", headers=headers).json()["data"]
        assert len([a for a in authors_again if a["name"] == author]) == 1
    finally:
        client.request("DELETE", "/api/follow", params={"name": author}, headers=headers)


def test_author_news_pagination(client):
    page1 = client.get(
        "/api/follow/news", params={"name": "海南日报", "page": 1, "pageSize": 5}
    ).json()["data"]
    page2 = client.get(
        "/api/follow/news", params={"name": "海南日报", "page": 2, "pageSize": 5}
    ).json()["data"]
    assert 0 < len(page1["list"]) <= 5
    assert not {i["id"] for i in page1["list"]} & {i["id"] for i in page2["list"]}


def test_follow_requires_login(client):
    assert client.get("/api/follow/authors").status_code == 401


def test_can_follow_multiple_authors(client, temp_user):
    """回归：唯一索引曾漏 target_name，导致一个用户只能关注一个作者。"""
    headers = _auth(temp_user)
    names = ["海南日报", "人民日报", "科技日报"]

    try:
        for name in names:
            resp = client.post("/api/follow", params={"name": name}, headers=headers)
            assert resp.status_code == 200
            assert resp.json()["data"]["following"] is True, f"关注 {name} 应该是新增"

        authors = client.get("/api/follow/authors", headers=headers).json()["data"]
        got = {a["name"] for a in authors}
        assert set(names) <= got, f"期望全部关注成功，实际只有 {got}"
    finally:
        for name in names:
            client.request("DELETE", "/api/follow", params={"name": name}, headers=headers)
