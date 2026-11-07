"""新闻接口的契约测试。

重点盯住三件容易回归的事：
1. 列表返回字段固定（不能随缓存命中/未命中变化，也不能带 content）；
2. 分页顺序稳定、不重复；
3. 参数错误走统一响应体，而不是 FastAPI 原生的 {"detail": [...]}。
"""

import pytest

LIST = "/api/news"

EXPECTED_FIELDS = {
    "id",
    "title",
    "description",
    "image",
    "author",
    "categoryId",
    "views",
    "publishTime",
}


def test_list_returns_unified_body_and_stable_fields(client):
    resp = client.get(LIST, params={"categoryId": 1, "page": 1, "pageSize": 2})
    assert resp.status_code == 200

    body = resp.json()
    assert set(body) == {"code", "message", "data"}
    assert body["code"] == 200

    items = body["data"]["list"]
    assert len(items) == 2
    assert set(items[0]) == EXPECTED_FIELDS
    # 列表不返回正文：修复前「冷缓存带 content、热缓存不带」
    assert "content" not in items[0]
    assert isinstance(body["data"]["total"], int)
    assert isinstance(body["data"]["hasMore"], bool)


def test_list_sorted_by_publish_time_desc(client):
    resp = client.get(LIST, params={"categoryId": 1, "page": 1, "pageSize": 10})
    times = [item["publishTime"] for item in resp.json()["data"]["list"]]
    assert times == sorted(times, reverse=True)


def test_pagination_has_no_duplicates(client):
    ids = []
    for page in (1, 2, 3):
        resp = client.get(LIST, params={"categoryId": 1, "page": page, "pageSize": 5})
        ids.extend(item["id"] for item in resp.json()["data"]["list"])
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "params, keyword",
    [
        ({"categoryId": 1, "pageSize": 0}, "pageSize"),
        ({"categoryId": 1, "page": 0}, "page"),
        ({"categoryId": 1, "pageSize": 101}, "pageSize"),
        ({"pageSize": 10}, "categoryId"),
        ({"categoryId": 1, "page": "abc"}, "page"),
    ],
)
def test_invalid_params_use_unified_422(client, params, keyword):
    resp = client.get(LIST, params=params)
    assert resp.status_code == 422

    body = resp.json()
    assert body["code"] == 422
    assert keyword in body["message"]
    # 原生 422 的形状是 {"detail": [...]}，必须已经被统一处理器收掉
    assert "detail" not in body
    assert body["data"]["errors"]

    # 错误信息里绝不能回显用户提交的值（注册接口的 password 会走到同一条路径）
    assert "input" not in str(body)


def test_listing_unknown_category_returns_empty(client):
    resp = client.get(LIST, params={"categoryId": 99999, "page": 1, "pageSize": 5})
    assert resp.status_code == 200
    assert resp.json()["data"] == {"list": [], "total": 0, "hasMore": False}


def test_detail_not_found(client):
    resp = client.get("/api/news/999999")
    assert resp.status_code == 404
    assert resp.json() == {"code": 404, "message": "新闻不存在", "data": None}


def test_protected_endpoint_without_token(client):
    resp = client.get("/api/user/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401
    assert "令牌" in body["message"]


def test_request_id_header_is_set(client):
    assert client.get("/").headers.get("x-request-id")


def test_cors_rejects_unknown_origin(client):
    resp = client.get("/", headers={"Origin": "https://evil.example.com"})
    assert resp.headers.get("access-control-allow-origin") is None
