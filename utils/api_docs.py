"""OpenAPI 公共错误响应声明。

FastAPI 默认只会为每个接口生成 200 和 422。项目实际还会返回
401/403/404/409/429 等状态码，这里按路由类型集中声明，避免文档
与实际行为不一致。
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from schemas.common import ApiErrorResponse

_ERROR_DESCRIPTIONS = {
    400: "请求参数或业务状态不合法",
    401: "未登录、令牌无效或已过期",
    403: "没有操作权限，或账号已被禁用",
    404: "资源不存在",
    409: "唯一约束冲突，例如用户名或收藏记录已存在",
    422: "请求参数校验失败",
    429: "请求过于频繁，请稍后重试",
    500: "服务器内部错误",
    502: "上游大模型服务返回异常",
    503: "大模型服务未配置或暂时不可用",
}


def documented_errors(*status_codes: int) -> dict[int, dict]:
    """生成 APIRouter/路由装饰器可用的 responses 配置。"""

    return {
        code: {
            "model": ApiErrorResponse,
            "description": _ERROR_DESCRIPTIONS[code],
        }
        for code in status_codes
    }


AUTHENTICATED_ERRORS = documented_errors(401, 403, 404, 409, 422, 429)
PUBLIC_READ_ERRORS = documented_errors(404, 422)
ADMIN_ERRORS = documented_errors(401, 403, 404, 409, 422)
AI_ERRORS = documented_errors(400, 401, 404, 422, 429, 502, 503)


def setup_openapi(app: FastAPI) -> None:
    """生成更稳定的 operationId，并复用应用级文档元信息。

    FastAPI 默认的 operationId 由 Python 函数名和路径拼成，函数重命名后
    SDK 方法名也会跟着变化。这里统一为 `<tag>_<method>_<path>`，文档和
    代码生成工具都更容易消费。
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        if app.openapi_tags:
            schema["tags"] = app.openapi_tags
        for path, methods in schema.get("paths", {}).items():
            slug = path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
            for method, operation in methods.items():
                tag = (operation.get("tags") or ["api"])[0]
                operation["operationId"] = f"{tag}_{method}_{slug}"

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
