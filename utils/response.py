from collections.abc import Mapping

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(
    message: str = "success",
    data=None,
    *,
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
):
    """构造项目统一的成功响应。

    HTTP 状态码与响应体 code 保持一致，避免出现“HTTP 201 但 body.code=200”
    这种调用方难以判断的情况。创建资源时传 status_code=201 并提供 Location。
    """

    content = {"code": status_code, "message": message, "data": data}
    return JSONResponse(
        content=jsonable_encoder(content),
        status_code=status_code,
        headers=dict(headers) if headers else None,
    )
