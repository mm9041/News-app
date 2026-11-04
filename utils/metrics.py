"""进程内 Prometheus 指标 + 请求计时中间件。

指标存在进程内存里。单实例部署完全够用；多实例时 Prometheus 按实例抓取，
`rate()` 在聚合时天然除以实例数，结果仍然正确。需要跨实例看总数时再上 OTel。

⚠️ path 用的是路由模板（/api/news/detail/{id}），不是原始 URL：
原始 URL 每个新闻 id 产生一条时间序列，基数会爆炸，把 Prometheus 撑爆。
"""

import time
from collections import defaultdict

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# defaultdict 必须用：+= 会先 __getitem__ 再 __setitem__，
# 普通 dict 在第一次计数时就 KeyError
_histogram: defaultdict[str, list[int]] = defaultdict(lambda: [0] * (len(BUCKETS) + 1))
_summary: defaultdict[str, list[float]] = defaultdict(lambda: [0.0, 0])
_status_count: defaultdict[str, int] = defaultdict(int)


def observe(method: str, path: str, status_code: int, duration: float) -> None:
    key = f"{method} {path}"
    buckets = _histogram.setdefault(key, [0] * (len(BUCKETS) + 1))
    for index, bound in enumerate(BUCKETS):
        if duration <= bound:
            buckets[index] += 1
            break
    else:
        buckets[-1] += 1

    total, count = _summary.setdefault(key, [0.0, 0])
    _summary[key] = [total + duration, count + 1]

    status_key = f"{method} {path} {status_code // 100}xx"
    _status_count[status_key] += 1


def render_metrics() -> str:
    lines = [
        "# HELP http_request_duration_seconds HTTP 请求耗时直方图",
        "# TYPE http_request_duration_seconds histogram",
    ]
    for key, buckets in _histogram.items():
        method, path = key.split(" ", 1)
        cumulative = 0
        for index, bound in enumerate(BUCKETS):
            cumulative += buckets[index]
            lines.append(
                f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bound}"}} {cumulative}'
            )
        cumulative += buckets[-1]
        lines.append(
            f'http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {cumulative}'
        )
        total, count = _summary.get(key, [0.0, 0])
        lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}')
        lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}')

    lines.append("# HELP http_requests_total HTTP 请求计数（按状态段）")
    lines.append("# TYPE http_requests_total counter")
    for key, count in _status_count.items():
        method, path, code = key.rsplit(" ", 2)
        lines.append(f'http_requests_total{{method="{method}",path="{path}",code="{code}"}} {count}')

    return "\n".join(lines) + "\n"


class MetricsMiddleware:
    """纯 ASGI 中间件：统计每个请求的耗时与状态码。

    path 取路由模板，来自 request.scope["route"]（Starlette 在路由匹配后写入）。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        route = scope.get("route")
        path = route.path if route else scope["path"]
        observe(scope["method"], path, status_holder["code"], time.perf_counter() - start)
