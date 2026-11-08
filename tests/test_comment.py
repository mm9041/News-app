"""评论：发布、列表、删除权限。

注意 fixture 的分工：
- `comment` 的作者是 `other_user`
- `temp_user` 用来验证「不能删别人的」
- `admin_user` 基于 temp_user 提权，用来验证「管理员能删任意」
这样三种身份互不重叠，权限断言才有意义。
"""

import pytest

# 示例数据里的一条新闻，只作为评论挂载点
NEWS_ID = 45


def _add(client, token, content, news_id=NEWS_ID):
    return client.post(
        "/api/comment",
        json={"newsId": news_id, "content": content},
        headers={"Authorization": token},
    )


def _list(client, token=None, news_id=NEWS_ID, page_size=None):
    headers = {"Authorization": token} if token else {}
    params = {"newsId": news_id}
    if page_size:
        params["pageSize"] = page_size
    return client.get("/api/comment", params=params, headers=headers)


@pytest.fixture
def comment(client, other_user):
    resp = _add(client, other_user["token"], "pytest 评论内容")
    assert resp.status_code == 201, resp.text
    assert resp.headers["Location"] == f"/api/comment/{resp.json()['data']['id']}"
    comment_id = resp.json()["data"]["id"]

    yield {"id": comment_id, "token": other_user["token"], "user_id": other_user["user_id"]}

    # 用例可能已经删掉了，404 也无所谓
    client.delete(f"/api/comment/{comment_id}", headers={"Authorization": other_user["token"]})


def test_add_requires_login(client):
    resp = client.post("/api/comment", json={"newsId": NEWS_ID, "content": "hi"})
    assert resp.status_code == 401


def test_add_and_list(client, temp_user):
    resp = _add(client, temp_user["token"], "列表里应该能看到我")
    assert resp.status_code == 201
    comment_id = resp.json()["data"]["id"]

    try:
        listing = _list(client, temp_user["token"]).json()["data"]
        item = next(i for i in listing["list"] if i["id"] == comment_id)

        assert item["content"] == "列表里应该能看到我"
        assert item["user"]["username"] == temp_user["username"]
        assert item["canDelete"] is True
    finally:
        client.delete(f"/api/comment/{comment_id}", headers={"Authorization": temp_user["token"]})


def test_guest_can_read_but_not_delete(client, comment):
    resp = _list(client)
    assert resp.status_code == 200

    item = next((i for i in resp.json()["data"]["list"] if i["id"] == comment["id"]), None)
    assert item is not None
    assert item["canDelete"] is False


def test_delete_own_comment(client, comment):
    resp = client.delete(f"/api/comment/{comment['id']}", headers={"Authorization": comment["token"]})
    assert resp.status_code == 200


def test_cannot_delete_others_comment(client, comment, temp_user):
    resp = client.delete(f"/api/comment/{comment['id']}", headers={"Authorization": temp_user["token"]})
    assert resp.status_code == 403
    assert "只能删除自己的评论" in resp.json()["message"]


def test_admin_can_delete_any_comment(client, comment, admin_user):
    resp = client.delete(f"/api/comment/{comment['id']}", headers={"Authorization": admin_user["token"]})
    assert resp.status_code == 200


def test_list_is_newest_first(client, temp_user):
    ids = []
    try:
        for i in range(3):
            resp = _add(client, temp_user["token"], f"顺序测试 {i}")
            ids.append(resp.json()["data"]["id"])

        listing = _list(client, temp_user["token"]).json()["data"]["list"]
        got = [item["id"] for item in listing if item["id"] in ids]
        assert got == sorted(ids, reverse=True)
    finally:
        for comment_id in ids:
            client.delete(f"/api/comment/{comment_id}", headers={"Authorization": temp_user["token"]})


def test_total_includes_replies_and_paging_uses_roots(client, temp_user):
    """total 要含回复；hasMore 只看一级评论，不能被回复数量带偏。

    先取基线再断言增量，避免依赖 45 号新闻里已有的种子评论。
    """
    headers = {"Authorization": temp_user["token"]}
    baseline = _list(client).json()["data"]["total"]

    root = _add(client, temp_user["token"], "计数用一级评论")
    assert root.status_code == 201
    root_id = root.json()["data"]["id"]

    try:
        for i in range(2):
            resp = client.post(
                "/api/comment",
                json={"newsId": NEWS_ID, "content": f"计数用回复 {i}", "parentId": root_id},
                headers=headers,
            )
            assert resp.status_code == 201, resp.text

        data = _list(client, page_size=100).json()["data"]
        # 1 条一级 + 2 条回复，全部计入总数
        assert data["total"] == baseline + 3
        # 一级评论一页就能装下，回复再多也不能说「还有下一页」
        assert data["hasMore"] is False
    finally:
        client.delete(f"/api/comment/{root_id}", headers=headers)


@pytest.mark.parametrize("content", ["", "   ", "x" * 501])
def test_invalid_content(client, temp_user, content):
    resp = _add(client, temp_user["token"], content)
    assert resp.status_code == 422
    assert resp.json()["code"] == 422


def test_comment_on_missing_news(client, temp_user):
    resp = _add(client, temp_user["token"], "hi", news_id=999999)
    assert resp.status_code == 404
    assert "新闻不存在" in resp.json()["message"]
