"""AI 接口的入参约束。

只测「请求还没发到上游就被拦下」的分支，不产生真实调用费用。
"""

import pytest


def _post(client, token, payload):
    return client.post("/api/ai/chat", json=payload, headers={"Authorization": token})


def test_single_message_too_long(client, temp_user):
    resp = _post(client, temp_user["token"], {"messages": [{"role": "user", "content": "x" * 9000}]})
    assert resp.status_code == 422
    assert "8000" in resp.json()["message"]


def test_total_length_limit(client, temp_user):
    payload = {"messages": [{"role": "user", "content": "x" * 8000}] * 3}
    resp = _post(client, temp_user["token"], payload)
    assert resp.status_code == 422
    assert "对话内容过长" in resp.json()["message"]


def test_invalid_role(client, temp_user):
    resp = _post(client, temp_user["token"], {"messages": [{"role": "hacker", "content": "hi"}]})
    assert resp.status_code == 422
    assert "role" in resp.json()["message"]


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": ""}]])
def test_empty_messages_rejected(client, temp_user, messages):
    resp = _post(client, temp_user["token"], {"messages": messages})
    assert resp.status_code == 422


def test_model_outside_allowlist(client, temp_user):
    resp = _post(
        client,
        temp_user["token"],
        {"messages": [{"role": "user", "content": "hi"}], "model": "gpt-4o"},
    )
    assert resp.status_code == 400
    assert "不支持模型" in resp.json()["message"]


def test_chat_requires_login(client):
    resp = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 401
