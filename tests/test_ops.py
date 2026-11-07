"""运维端点：/health 的分级语义、/metrics 的访问控制。

/metrics 原来完全开放，等于把 QPS、慢查询、错误率这些内部信息挂在公网上。
现在的规则是「配了 token 就验 token，没配只认本机直连」。
"""

import main


def test_health_reports_dependencies(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("up", "degraded")
    assert {"mysql", "redis"} <= set(body["checks"])


def test_metrics_requires_configured_token(client, monkeypatch):
    """配了 token：不带 / 带错 → 403，带对 → 200（header 和 query 两种传法都支持）。"""
    monkeypatch.setattr(main, "METRICS_TOKEN", "s3cret-token")

    assert client.get("/metrics").status_code == 403
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 403

    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
    assert ok.status_code == 200
    assert "text/plain" in ok.headers["content-type"]

    ok2 = client.get("/metrics", params={"token": "s3cret-token"})
    assert ok2.status_code == 200


def test_metrics_rejects_forwarded_request_without_token(client, monkeypatch):
    """没配 token 时，任何带 X-Forwarded-For 的请求一律拒绝。

    容器里 uvicorn 开了 --proxy-headers 且信任所有来源，
    伪造 `X-Forwarded-For: 127.0.0.1` 就能把 client 变成回环地址 ——
    所以这里只认「没有转发头」的直连请求。
    """
    monkeypatch.setattr(main, "METRICS_TOKEN", "")

    resp = client.get("/metrics", headers={"X-Forwarded-For": "127.0.0.1"})
    assert resp.status_code == 403


def test_openapi_documents_rest_contract(client):
    """文档必须反映真实资源路径、创建状态码和常见错误。"""
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "新闻资讯 API"
    assert spec["info"]["version"] == "1.0.0"

    paths = spec["paths"]
    assert "patch" in paths["/api/user/me"]
    assert "/api/user" not in paths, "旧 PATCH 别名只保留运行时兼容，不应继续污染文档"
    assert "patch" in paths["/api/notification/{notification_id}"]
    assert "/api/notification/{notification_id}/read" not in paths
    assert "patch" in paths["/api/admin/users/{user_id}"]
    assert "/api/admin/users/{user_id}/ban" not in paths

    register = paths["/api/user/register"]["post"]
    assert "201" in register["responses"]
    assert "409" in register["responses"]
    assert register["operationId"] == "user_post_api_user_register"

    favorite = paths["/api/favorite"]["post"]
    assert "201" in favorite["responses"]
    assert "409" in favorite["responses"]
