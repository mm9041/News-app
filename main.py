import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache import view_counter
from crud.news_views import flush_view_deltas
from routers import news, users, favorite, history, ai, admin, comment
from utils.exception_handlers import register_exception_handlers
from utils.logger import get_logger, setup_logging
from utils.middleware import RequestIdMiddleware

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


app = FastAPI(lifespan=lifespan)

# uvicorn main:app --reload
# netstat -ano | findstr :8000


register_exception_handlers(app)

# 注意顺序：add_middleware 是「后加的在外层」。CORS 必须最外层，
# 否则中间件内层抛出的异常响应不会带 CORS 头，前端只会看到 net::ERR_FAILED。
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,  # 用 Authorization 头，不依赖 cookie
    allow_methods=["*"],
    allow_headers=["*"],
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
