"""AI 会话：创建、列表、详情、越权与删除。

不调真实大模型（那会产生费用且依赖外网），只测会话本身的 CRUD。
"""

import pytest


def _auth(user):
    return {"Authorization": user["token"]}


def test_conversation_requires_login(client):
    assert client.get("/api/ai/conversations").status_code == 401


def test_create_and_detail(client, temp_user):
    headers = _auth(temp_user)

    resp = client.post("/api/ai/conversations", json={"title": "测试会话"}, headers=headers)
    assert resp.status_code == 200
    conv_id = resp.json()["data"]["id"]

    detail = client.get(f"/api/ai/conversations/{conv_id}", headers=headers).json()["data"]
    assert detail["title"] == "测试会话"
    assert detail["messages"] == []

    client.delete(f"/api/ai/conversations/{conv_id}", headers=headers)


def test_empty_conversation_not_listed(client, temp_user):
    """点过「新对话」但没提问的会话不该出现在历史里。"""
    headers = _auth(temp_user)
    conv_id = client.post("/api/ai/conversations", json={"title": "空会话"}, headers=headers).json()["data"]["id"]

    try:
        listing = client.get("/api/ai/conversations", headers=headers).json()["data"]
        assert all(item["id"] != conv_id for item in listing["list"])
    finally:
        client.delete(f"/api/ai/conversations/{conv_id}", headers=headers)


def test_conversation_with_message_is_listed(client, temp_user, db):
    headers = _auth(temp_user)
    conv_id = client.post("/api/ai/conversations", json={"title": "有消息"}, headers=headers).json()["data"]["id"]

    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO ai_chat (user_id, conversation_id, message, response) VALUES (%s, %s, %s, %s)",
                (temp_user["user_id"], conv_id, "你好", "你好呀"),
            )

        listing = client.get("/api/ai/conversations", headers=headers).json()["data"]
        item = next((i for i in listing["list"] if i["id"] == conv_id), None)
        assert item is not None
        assert item["messageCount"] == 1

        detail = client.get(f"/api/ai/conversations/{conv_id}", headers=headers).json()["data"]
        # 一轮问答展开成 user + assistant 两条
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][0]["content"] == "你好"
    finally:
        client.delete(f"/api/ai/conversations/{conv_id}", headers=headers)


def test_cannot_touch_others_conversation(client, temp_user, other_user):
    headers = _auth(temp_user)
    conv_id = client.post("/api/ai/conversations", json={"title": "私有"}, headers=headers).json()["data"]["id"]

    try:
        assert client.get(f"/api/ai/conversations/{conv_id}", headers=_auth(other_user)).status_code == 404
        assert client.delete(f"/api/ai/conversations/{conv_id}", headers=_auth(other_user)).status_code == 404
    finally:
        client.delete(f"/api/ai/conversations/{conv_id}", headers=headers)


def test_delete_removes_messages(client, temp_user, db):
    headers = _auth(temp_user)
    conv_id = client.post("/api/ai/conversations", json={"title": "将被删"}, headers=headers).json()["data"]["id"]

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO ai_chat (user_id, conversation_id, message, response) VALUES (%s, %s, %s, %s)",
            (temp_user["user_id"], conv_id, "问", "答"),
        )

    assert client.delete(f"/api/ai/conversations/{conv_id}", headers=headers).status_code == 200

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ai_chat WHERE conversation_id=%s", (conv_id,))
        assert cur.fetchone()[0] == 0


@pytest.mark.parametrize("path", ["/api/ai/conversations/999999"])
def test_missing_conversation(client, temp_user, path):
    assert client.get(path, headers=_auth(temp_user)).status_code == 404
