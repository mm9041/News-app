"""可观测性：依赖健康探测 + 慢查询日志。

慢查询日志挂在 SQLAlchemy 的 sync engine 事件上 —— AsyncSession 底层就是它，
所有通过 ORM 的查询（包括 async）都会走到这两个事件。
"""

import time

from sqlalchemy import event, text

from config.cache_conf import redis_client
from config.db_conf import async_engine
from utils.logger import get_logger

logger = get_logger(__name__)

SLOW_QUERY_MS = 200


def setup_slow_query_logging() -> None:
    """超过阈值的 SQL 连同耗时打 warning，方便与 request_id 关联定位。"""

    @event.listens_for(async_engine.sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        context._query_start = time.perf_counter()

    @event.listens_for(async_engine.sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        elapsed = time.perf_counter() - getattr(context, "_query_start", time.perf_counter())
        if elapsed * 1000 >= SLOW_QUERY_MS:
            logger.warning("慢查询 %.0fms：%s", elapsed * 1000, " ".join(statement.split())[:300])


async def probe_dependencies(db) -> dict:
    """逐个探测依赖，返回 {名称: {ok, 耗时ms, 错误}}。"""
    checks: dict[str, dict] = {}

    start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        checks["mysql"] = {"ok": True, "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:
        checks["mysql"] = {"ok": False, "error": str(exc)[:200]}

    start = time.perf_counter()
    try:
        await redis_client.ping()
        checks["redis"] = {"ok": True, "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": str(exc)[:200]}

    return checks
