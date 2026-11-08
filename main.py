import asyncio
import os
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from cache import view_counter
from config.db_conf import AsyncSessionLocal
from crud.news_views import flush_view_deltas
from routers import admin, ai, comment, favorite, follow, history, news, notification, source, tag, upload, users
from utils.api_docs import setup_openapi
from utils.exception_handlers import register_exception_handlers
from utils.logger import get_logger, setup_logging
from utils.metrics import MetricsMiddleware, render_metrics
from utils.middleware import RequestIdMiddleware
from utils.observability import probe_dependencies, setup_slow_query_logging

BASE_DIR = Path(__file__).resolve().parent

# 上面 import config 时 .env 已经加载，这里读 LOG_LEVEL 才拿得到
setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

# 阅读量增量回写数据库的间隔（秒）
VIEW_FLUSH_INTERVAL = float(os.getenv("VIEW_FLUSH_INTERVAL", "30"))


def _allowed_origins() -> list[str]:
    """CORS 白名单。

    之前是 allow_origins=["*"] + allow_credentials=True —— 实测会把任意 Origin
    （包括 https://evil.example.com）原样回显并允许携带凭证。本项目用
    Authorization 头而不是 cookie，暂时没有实际危害，但一旦将来改成 cookie
    就直接变成 CSRF 缺口，不如现在就收紧。
    """
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    # 开发默认值：Vite 的 5173 / 端口被占用时顺延的 5174
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]


async def _view_flush_loop() -> None:
    """后台定时把 Redis 里累计的阅读量增量写回数据库。

    单进程部署下直接跑；如果将来用多 worker，需要加分布式锁，否则多个进程
    会同时扫到同一批增量（DECRBY 只能保证不重复扣，写库仍可能重复）。
    """
    while True:
        await asyncio.sleep(VIEW_FLUSH_INTERVAL)
        try:
            await flush_view_deltas()
        except Exception as e:
            logger.error("阅读量回写失败：%s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_view_flush_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        # 退出前把残留增量刷掉，否则重启会丢掉最后一次回写之后的阅读量
        try:
            await flush_view_deltas()
        except Exception as e:
            logger.error("退出前回写阅读量失败：%s", e)
        await view_counter.close()


API_DESCRIPTION = """
移动端优先的新闻资讯 API。

所有业务响应统一为 `{code, message, data}`：
- 成功时 HTTP 状态码与 `code` 一致；
- 创建资源返回 `201` 并通过 `Location` 指向新资源；
- 参数错误、未登录、权限不足、资源不存在、冲突和限流分别返回
  `422 / 401 / 403 / 404 / 409 / 429`。

认证支持两种方式：浏览器使用 httpOnly Cookie `access_token`，
脚本和测试可使用 `Authorization` 请求头，裸 token 或 `Bearer token` 均可。
"""

OPENAPI_TAGS = [
    {"name": "news", "description": "新闻列表、搜索、详情、推荐与点赞"},
    {"name": "user", "description": "注册、登录、当前用户与资料修改"},
    {"name": "favorite", "description": "新闻收藏"},
    {"name": "history", "description": "浏览历史"},
    {"name": "comment", "description": "两级评论与回复"},
    {"name": "notification", "description": "评论/点赞的站内通知"},
    {"name": "tag", "description": "标签与标签新闻"},
    {"name": "follow", "description": "关注作者与作者新闻"},
    {"name": "source", "description": "报纸来源与来源新闻"},
    {"name": "ai", "description": "AI 对话、会话与聊天记录"},
    {"name": "upload", "description": "图片上传"},
    {"name": "admin", "description": "新闻、用户与统计管理"},
]

# /docs 的 Swagger UI 默认从 jsdelivr 加载，国内网络会 SSL 失败导致白屏。
# FastAPI 构造函数没有 swagger_js_url/swagger_css_url 参数（会被静默忽略），
# 必须禁用默认 /docs，再用 get_swagger_ui_html 自定义资源地址。
app = FastAPI(
    title="新闻资讯 API",
    version="1.0.0",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
setup_openapi(app)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.17.14/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.17.14/swagger-ui.css",
        swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    )


# uvicorn main:app --reload
# netstat -ano | findstr :8000


register_exception_handlers(app)

# 注意顺序：add_middleware 是「后加的在外层」。CORS 必须最外层，
# 否则中间件内层抛出的异常响应不会带 CORS 头，前端只会看到 net::ERR_FAILED。
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    # 登录 token 走 httpOnly cookie，跨域请求需要带上凭证。
    # allow_origins 必须是显式白名单（上面已经收紧），不能用 "*"。
    allow_credentials=True,  # 允许浏览器在跨域请求中携带凭证（Cookie、Authorization 头等），并允许前端读取带凭证的响应
    allow_methods=["*"],
    allow_headers=["*"],
    # 必须显式暴露自定义响应头，否则跨域时 fetch 读不到它：
    # AIChat.vue 靠 X-Conversation-Id 拿新建会话的 id，读不到就会在下一轮
    # 又开一个新会话（同源部署时不受影响，所以这个坑只在开发环境暴露）。
    # Location 需要暴露给跨域客户端，否则创建资源后读不到新地址。
    expose_headers=["X-Conversation-Id", "X-Request-ID", "Location"],
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(news.router)
app.include_router(users.router)
app.include_router(favorite.router)
app.include_router(history.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(comment.router)
app.include_router(upload.router)
app.include_router(notification.router)
app.include_router(tag.router)
app.include_router(follow.router)
app.include_router(source.router)


# ---------------------------- 可观测性 ----------------------------


@app.get("/health")
async def health(strict: bool = Query(False, description="严格模式：Redis 不可用也算失败")):
    """依赖探测。

    MySQL 是硬依赖，挂了返回 503。
    Redis 是可选的加速层 —— 缓存能降级回源、限流故障时放行、阅读量退回直写库，
    所以默认只在响应体里标 `degraded` 但仍返回 200。否则负载均衡 / K8s 探针
    会把一个功能完全正常的实例摘掉（实测过：Redis 一停，业务接口全 200，/health 却 503）。
    需要"Redis 也必须活"的探针传 `?strict=true`。
    """
    async with AsyncSessionLocal() as db:
        checks = await probe_dependencies(db)

    mysql_ok = checks["mysql"]["ok"]
    redis_ok = checks["redis"]["ok"]

    if not mysql_ok:
        status_text = "down"
    elif redis_ok:
        status_text = "up"
    else:
        status_text = "degraded"

    ok = mysql_ok and (redis_ok or not strict)
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": status_text, "checks": checks},
    )


# /metrics 的访问控制：配了 token 就认 token；没配则只允许本机直连。
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "").strip()


def _metrics_allowed(request: Request) -> bool:
    """指标端点的访问控制。

    1. 配了 `METRICS_TOKEN`：必须带 `Authorization: Bearer <token>` 或 `?token=`；
    2. 没配：只允许**本机直连** —— client 是回环地址，且请求里没有 `X-Forwarded-For`。

    为什么不按「内网网段」放行：容器里 uvicorn 开了 `--proxy-headers` 且
    `--forwarded-allow-ips=*`，任何人都能伪造 `X-Forwarded-For: 127.0.0.1`
    让 client 变成回环地址。所以只要出现转发头就一律不认，必须配 token。
    """
    if METRICS_TOKEN:
        supplied = request.headers.get("authorization", "")
        if supplied[:7].lower() == "bearer ":
            supplied = supplied[7:].strip()
        supplied = supplied or request.query_params.get("token", "")
        return secrets.compare_digest(supplied, METRICS_TOKEN)

    if request.headers.get("x-forwarded-for"):
        return False
    client_host = request.client.host if request.client else ""
    return client_host in ("127.0.0.1", "::1", "localhost")


@app.get("/metrics")
async def metrics_endpoint(request: Request):
    """Prometheus 抓取端点（文本格式）。

    默认只对本机开放；要让 Prometheus 从别的机器/容器抓，就在 .env 里配 METRICS_TOKEN。
    """
    if not _metrics_allowed(request):
        raise HTTPException(status_code=403, detail="指标端点需要授权，请配置 METRICS_TOKEN")
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")


setup_slow_query_logging()

# 上传的图片直接由 FastAPI 托管；生产环境应该换成 nginx / 对象存储
UPLOAD_ROOT = BASE_DIR / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")
