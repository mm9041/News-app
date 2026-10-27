from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_database
from crud import users


async def get_current_user(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        db: AsyncSession = Depends(get_database)
):
    """从 Authorization 头取出 token 并查出对应的用户。

    这个头声明成**可选**（Header(None)）是有意为之：如果写成 Header(...)，
    FastAPI 会在进入函数之前就用它自己的校验把请求拦下，返回

        422 {"detail":[{"type":"missing","loc":["header","Authorization"],...}]}

    既不符合项目统一的 {code, message, data}，前端也读不到 message。
    所以改成在函数里自己判断，统一抛 401。

    token 放裸值即可；带了 "Bearer " 前缀也兼容（下面直接 replace 掉）。
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供令牌，请先登录"
        )

    # 裸 token 与 "Bearer xxx" 都接受。用 removeprefix 而不是 replace：
    # replace 会把 token 中间出现的 "Bearer " 也一并删除，行为不可预期。
    token = authorization.strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()

    user = await users.get_user_by_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌或已经过期的令牌"
        )

    return user
