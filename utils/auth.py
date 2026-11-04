import os
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_database
from crud import users
from models.users import User

# 浏览器走 httpOnly cookie，脚本 / curl 仍可用 Authorization 头。
# 两条通道并存：前端不再把 token 写进 localStorage，
# 但测试和第三方调用方照旧能带 header（不用为了 cookie 改一遍所有用例）。
TOKEN_COOKIE_NAME = "access_token"
TOKEN_TTL_SECONDS = 7 * 24 * 3600

# 上 HTTPS 后把它置为 true（.env 里配 COOKIE_SECURE=true）；
# 本地 http 下必须为 false，否则浏览器直接不保存 cookie。
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes", "on")


def set_token_cookie(response, token: str) -> None:
    """把 token 写进 httpOnly cookie。

    - httponly：JS 读不到，XSS 也就偷不走（这是本次改造的全部意义）
    - samesite=lax：跨站 POST 不带 cookie，挡掉大部分 CSRF；
      同站不同端口（5173 -> 8000）仍会带上
    - secure：见上面的 COOKIE_SECURE
    """
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        max_age=TOKEN_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def clear_token_cookie(response) -> None:
    response.delete_cookie(TOKEN_COOKIE_NAME, path="/")


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization 头取出 token。

    裸 token 与 "Bearer xxx" 都接受。用切片而不是 replace：
    replace 会把 token 中间出现的 "Bearer " 也一并删掉，行为不可预期。
    """
    if not authorization:
        return None
    token = authorization.strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    return token or None


def token_from_request(authorization: Optional[str], access_token: Optional[str]) -> Optional[str]:
    """按「header 优先、cookie 兜底」的顺序取 token。"""
    return _extract_token(authorization) or _extract_token(access_token)


async def get_current_user(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        access_token: Optional[str] = Cookie(None, alias=TOKEN_COOKIE_NAME),
        db: AsyncSession = Depends(get_database)
):
    """从 Authorization 头或 httpOnly cookie 取出 token 并查出用户。

    头声明成**可选**（Header(None)）是有意为之：如果写成 Header(...)，
    FastAPI 会在进入函数之前就用它自己的校验把请求拦下，返回

        422 {"detail":[{"type":"missing","loc":["header","Authorization"],...}]}

    既不符合项目统一的 {code, message, data}，前端也读不到 message。
    所以改成在函数里自己判断，统一抛 401。
    """
    token = token_from_request(authorization, access_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供令牌，请先登录"
        )

    user = await users.get_user_by_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌或已经过期的令牌"
        )
    if user.status:
        # 管理员禁用的账号：身份对、但被拉黑，返回 403 而不是 401（不该引导去登录）
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员"
        )

    return user


async def get_optional_user(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        access_token: Optional[str] = Cookie(None, alias=TOKEN_COOKIE_NAME),
        db: AsyncSession = Depends(get_database)
) -> Optional[User]:
    """可选登录：没带凭证、或 token 失效时都返回 None，不抛 401。

    评论列表这类「游客能看、登录后才决定能不能删」的接口用它。
    """
    token = token_from_request(authorization, access_token)
    if not token:
        return None
    user = await users.get_user_by_token(db, token)
    # 禁用账号视为游客：能看公开内容，但拿不到任何需要登录的能力
    return None if (not user or user.status) else user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """管理后台专用依赖：先按普通用户鉴权，再校验管理员标记。

    返回 403 而不是 401：身份是有效的，只是没有权限。
    前端拿到 401 会清登录态并跳登录页，403 不应该触发这个逻辑。
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user
