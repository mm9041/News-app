import traceback

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette import status

# 开发模式：返回详细错误信息
# 生产模式：返回简化错误信息
DEBUG_MODE = False  # 教学项目保持开启

# loc 的第一个元素是错误来源，不属于字段名
_LOC_SOURCES = ("query", "path", "header", "body", "cookie")


def _field_name(err: dict) -> str:
    """从 loc 里取出人能看懂的字段名，例如 ('query','pageSize') -> 'pageSize'。"""
    parts = [str(part) for part in err.get("loc", ()) if part not in _LOC_SOURCES]
    return ".".join(parts) or "请求参数"


def _humanize_validation_error(err: dict) -> str:
    """把 Pydantic 的英文错误码翻成一句可以直接展示给用户的中文。

    默认的 422 响应体是 {"detail": [{"type": ..., "loc": [...], "input": ...}]}，
    既不统一、前端也读不到 message；而且 input 里可能带着用户刚提交的密码。
    这里只保留字段名和可读提示，不回显任何请求值。
    """
    field = _field_name(err)
    err_type = err.get("type", "")
    ctx = err.get("ctx") or {}

    if err_type == "missing":
        return f"缺少必填参数：{field}"
    if err_type == "greater_than_equal":
        return f"参数 {field} 不能小于 {ctx.get('ge')}"
    if err_type == "less_than_equal":
        return f"参数 {field} 不能大于 {ctx.get('le')}"
    if err_type.startswith("int_"):
        return f"参数 {field} 必须是整数"
    if err_type.startswith("float_"):
        return f"参数 {field} 必须是数字"
    if err_type == "string_too_short":
        return f"参数 {field} 长度不能少于 {ctx.get('min_length')} 个字符"
    if err_type == "string_too_long":
        return f"参数 {field} 长度不能超过 {ctx.get('max_length')} 个字符"
    if err_type == "literal_error":
        return f"参数 {field} 的取值不在允许范围内"
    if err_type == "bool_parsing":
        return f"参数 {field} 必须是布尔值"
    if err_type == "value_error":
        # 模型里的 @model_validator 抛 ValueError 时，Pydantic 会包成 "Value error, xxx"
        return (err.get("msg") or "取值不合法").removeprefix("Value error, ")
    if err_type == "json_invalid":
        return "请求体不是合法的 JSON"
    return f"参数 {field} 不合法：{err.get('msg') or '格式不正确'}"


async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    """把 FastAPI 默认的 422 收进项目统一的 {code, message, data} 结构。

    不注册这个处理器时，参数错误会绕过 http_exception_handler 直接返回
    {"detail": [...]}，前端按 res.data.message 取提示会拿到 undefined。
    """
    errors = [
        {"field": _field_name(err), "message": _humanize_validation_error(err)}
        for err in exc.errors()
    ]
    message = errors[0]["message"] if errors else "请求参数不合法"
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": message,
            "data": {"errors": errors},
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    处理 HTTPException 异常
    """
    # HTTPException 通常是业务逻辑主动抛出的，data 保持 None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None
        }
    )


# 约束名 -> 面向用户的文案。
#
# pymysql 的报错串形如 `Duplicate entry '3-45' for key 'favorite.user_news_unique'`，
# 只判断 "Duplicate entry" 会把「重复收藏」也说成「用户名已存在」——
# 实测踩过：同一篇新闻收藏两次，前端弹出"用户名已存在"。
# 顺序上把更具体的放前面（news_like 的唯一索引名里也含 news）。
_CONSTRAINT_MESSAGES = (
    ("username_UNIQUE", "用户名已存在"),
    ("phone_UNIQUE", "该手机号已被其他账号使用"),
    ("token_UNIQUE", "登录状态冲突，请重新登录"),
    ("user_news_like_unique", "已经点过赞了"),
    ("user_news_unique", "已经收藏过这条新闻了"),
    ("news_tag_unique", "同一篇新闻不能重复挂同一个标签"),
    ("name_UNIQUE", "名称已存在"),
)


def _integrity_detail(error_msg: str) -> str:
    for constraint, message in _CONSTRAINT_MESSAGES:
        if constraint in error_msg:
            return message
    if "FOREIGN KEY" in error_msg:
        return "关联数据不存在"
    if "Duplicate entry" in error_msg:
        # 命中了唯一索引但没匹配到具体约束名：按「重复提交」处理，
        # 至少不能说成是用户名的问题。
        return "数据已存在，请勿重复提交"
    return "数据约束冲突，请检查输入"


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    处理数据库完整性约束错误
    """
    error_msg = str(exc.orig)

    detail = _integrity_detail(error_msg)

    # 开发模式下返回详细错误信息
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": "IntegrityError",
            "error_detail": error_msg,
            "path": str(request.url)
        }

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": 400,
            "message": detail,
            "data": error_data
        }
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """
    处理 SQLAlchemy 数据库错误
    """
    # 开发模式下返回详细错误信息
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
            # 格式化异常信息为字符串，方便日志记录和调试
            "traceback": traceback.format_exc(),
            "path": str(request.url)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "数据库操作失败，请稍后重试",
            "data": error_data
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    处理所有未捕获的异常
    """
    # 开发模式下返回详细错误信息
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
            # 格式化异常信息为字符串，方便日志记录和调试
            "traceback": traceback.format_exc(),
            "path": str(request.url)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": error_data
        }
    )
