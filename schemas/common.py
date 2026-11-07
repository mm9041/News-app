"""API 通用响应模型。

这些模型主要服务于 OpenAPI 文档；实际响应由 JSONResponse 生成，
业务代码不依赖它们做二次序列化。统一在这里定义可以避免每个路由
重复声明错误结构和响应信封。
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiFieldError(BaseModel):
    """参数校验失败时的单个字段错误。"""

    field: str
    message: str


class ApiErrorData(BaseModel):
    """错误响应的 data 部分。

    404、409 等业务错误通常没有 data；422 会返回 errors 列表。
    """

    errors: list[ApiFieldError] = Field(default_factory=list)


class ApiResponse(BaseModel, Generic[T]):  # noqa: UP046 - Pydantic 泛型显式继承更稳妥
    """统一成功响应信封。"""

    code: int = 200
    message: str = "success"
    data: T | None = None


class ApiErrorResponse(BaseModel):
    """统一错误响应信封。"""

    code: int
    message: str
    data: ApiErrorData | dict[str, Any] | None = None
