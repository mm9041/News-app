"""请求级中间件。

用纯 ASGI 实现，而不是 `BaseHTTPMiddleware` / `@app.middleware("http")`：
后者会把响应包一层，对 SSE 流式接口（`/api/ai/chat`）存在缓冲风险 ——
表现是首字延迟变大，严重时整段回答一次性吐出来。
"""

import uuid

from starlette.datastructures import Headers, MutableHeaders

from utils.logger import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware:
    """给每个请求分配一个 id，写进日志上下文和响应头。

    客户端传了 `X-Request-ID` 就复用（方便跨服务串联），否则生成 12 位随机串。
    排查线上问题时，拿着响应头里的 id 就能 grep 出这个请求的全部日志。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)
