"""统一日志配置。

改造前后端用 `print` 输出错误，有三个问题：
1. 没有级别，线上想只看 error 做不到；
2. 没有时间戳，多个请求的输出交错后分不清先后；
3. 没有请求标识，一次失败的多行日志串不起来。

这里统一成一行一条、带 request_id 的格式。request_id 由
`utils/middleware.RequestIdMiddleware` 写进 contextvar，同一请求内的所有日志
自动带上同一个 id —— 不用逐层传参。
"""

import logging
import sys
from contextvars import ContextVar

# 默认 "-" 覆盖非请求上下文（启动、退出、后台回写任务）
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(request_id)s | %(name)s | %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: str = "INFO") -> None:
    """配置根 logger。重复调用是安全的（不会装多个 handler）。"""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
        handler.addFilter(RequestIdFilter())
        root.addHandler(handler)
    root.setLevel(level.upper())

    # 第三方库的 INFO 噪音太多，降到 WARNING
    for noisy in ("httpx", "httpcore", "aiomysql", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
