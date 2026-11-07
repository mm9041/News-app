"""收藏与浏览历史：404 前置判断、幂等语义、upsert 去重。

这两个模块原来都把「数据不存在」交给外键报错兜底，结果是：
- 收藏一条不存在的新闻 → 400「关联数据不存在」（应该是 404）；
- 重复收藏 → 400「用户名已存在」（约束文案一刀切）；
- 取消没收藏过的 → 404（弱网重试会弹错）；
- 历史记录「先查后插」，并发下能插出两条。
"""

NEWS_ID = 45
OTHER_NEWS_ID = 46
MISSING_NEWS_ID = 99999999


def _auth(user):
    return {"Authorization": user["token"]}


# ---------------------------------------------------------------- 收藏


def test_favorite_add_missing_news_returns_404(client, temp_user):
    resp = client.post("/api/favorite", json={"newsId": MISSING_NEWS_ID}, headers=_auth(temp_user))
    assert resp.status_code == 404
    assert "新闻" in resp.json()["message"]


def test_favorite_duplicate_message_is_about_favorite(client, temp_user):
    """重复收藏必须说「收藏过了」，不能说成「用户名已存在」。"""
    headers = _auth(temp_user)
    client.delete(f"/api/favorite/{NEWS_ID}", headers=headers)

    first = client.post("/api/favorite", json={"newsId": NEWS_ID}, headers=headers)
    assert first.status_code == 201
    assert first.headers["Location"] == f"/api/favorite/{NEWS_ID}"

    second = client.post("/api/favorite", json={"newsId": NEWS_ID}, headers=headers)
    assert second.status_code == 409
    message = second.json()["message"]
    assert "收藏" in message
    assert "用户名" not in message

    client.delete(f"/api/favorite/{NEWS_ID}", headers=headers)


def test_favorite_remove_is_idempotent(client, temp_user):
    """没收藏过也返回成功 —— 和点赞一样，弱网重试不该弹错。"""
    headers = _auth(temp_user)
    for _ in range(2):
        resp = client.delete(f"/api/favorite/{NEWS_ID}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["removed"] is False


def test_favorite_list_shape(client, temp_user):
    """列表项必须是 camelCase 契约，且不夹带 ORM 内部状态 / 正文。"""
    headers = _auth(temp_user)
    client.post("/api/favorite", json={"newsId": NEWS_ID}, headers=headers)

    try:
        data = client.get("/api/favorite", headers=headers).json()["data"]
        assert data["total"] == 1
        item = data["list"][0]

        assert item["id"] == NEWS_ID
        assert "favoriteId" in item and "favoriteTime" in item
        assert "categoryId" in item and "publishTime" in item
        assert "content" not in item
        assert "_sa_instance_state" not in item
    finally:
        client.delete(f"/api/favorite/{NEWS_ID}", headers=headers)


# ---------------------------------------------------------------- 浏览历史


def test_history_add_missing_news_returns_404(client, temp_user):
    resp = client.post("/api/history", json={"newsId": MISSING_NEWS_ID}, headers=_auth(temp_user))
    assert resp.status_code == 404


def test_history_add_is_idempotent(client, temp_user, db):
    """同一篇新闻看三次，库里只应留一条，且列表 total 是 1。"""
    headers = _auth(temp_user)
    for _ in range(3):
        resp = client.post("/api/history", json={"newsId": NEWS_ID}, headers=headers)
        assert resp.status_code == 200

    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM history WHERE user_id=%s AND news_id=%s",
            (temp_user["user_id"], NEWS_ID),
        )
        assert cur.fetchone()[0] == 1, "唯一索引 + upsert 应该只留一条"

    data = client.get("/api/history", headers=headers).json()["data"]
    assert data["total"] == 1
    item = data["list"][0]
    assert "historyId" in item and "viewTime" in item
    assert item["id"] == NEWS_ID
    assert "_sa_instance_state" not in item


def test_history_delete_takes_news_id(client, temp_user):
    """删除参数是新闻 id：删掉 A 不能连累 B。"""
    headers = _auth(temp_user)
    client.post("/api/history", json={"newsId": NEWS_ID}, headers=headers)
    client.post("/api/history", json={"newsId": OTHER_NEWS_ID}, headers=headers)

    resp = client.delete(f"/api/history/{NEWS_ID}", headers=headers)
    assert resp.status_code == 200

    ids = [item["id"] for item in client.get("/api/history", headers=headers).json()["data"]["list"]]
    assert NEWS_ID not in ids
    assert OTHER_NEWS_ID in ids
