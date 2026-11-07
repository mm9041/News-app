from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import users
from crud.users import create_token, create_user, get_user_by_username, update_user
from models.users import User
from schemas.common import ApiResponse
from schemas.users import (
    UserAuthResponse,
    UserChangePasswordRequest,
    UserInfoResponse,
    UserRegisterRequest,
    UserRequest,
    UserUpdateRequest,
)
from utils.api_docs import documented_errors
from utils.auth import (
    TOKEN_COOKIE_NAME,
    clear_token_cookie,
    get_current_user,
    set_token_cookie,
    token_from_request,
)
from utils.rate_limit import client_ip, enforce
from utils.response import success_response

router = APIRouter(prefix="/api/user", tags=["user"])
USER_ERRORS = documented_errors(401, 403, 409, 422, 429)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[UserAuthResponse],
    responses=documented_errors(409, 422, 429),
)
async def register(user_data: UserRegisterRequest, request: Request, db: AsyncSession = Depends(get_database)):
    # 防批量注册：同一 IP 每分钟最多 5 个账号
    await enforce(f"register:{client_ip(request)}", 5, 60, "注册过于频繁，请 1 分钟后再试")
    if await get_user_by_username(db, user_data.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户已存在")
    user = await create_user(db, user_data)
    token = await create_token(db, user.id)
    # 用户和令牌必须一起落库：token 写失败时回滚用户，否则该用户名会永久卡死
    await db.commit()
    response_data = UserAuthResponse(token=token, userInfo=UserInfoResponse.model_validate(user))
    response = success_response(
        data=response_data,
        message="注册成功",
        status_code=status.HTTP_201_CREATED,
        headers={"Location": "/api/user/me"},
    )
    # 同时下发 httpOnly cookie：浏览器后续请求自动带上，前端不用碰 token
    set_token_cookie(response, token)
    return response


@router.post(
    "/login",
    response_model=ApiResponse[UserAuthResponse],
    responses=documented_errors(401, 403, 422, 429),
)
async def login(user_data: UserRequest, request: Request, db: AsyncSession = Depends(get_database)):
    # 防暴力破解：同一 IP 每分钟最多 10 次尝试（成功与否都计数）
    await enforce(f"login:{client_ip(request)}", 10, 60, "登录尝试过于频繁，请 1 分钟后再试")
    user = await users.authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status:
        # 被管理员禁用的账号：不是密码错，别引导用户去改密码
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")
    token = await create_token(db, user.id)
    await db.commit()
    response_data = UserAuthResponse(token=token, userInfo=UserInfoResponse.model_validate(user))
    response = success_response(data=response_data, message="登录成功")
    set_token_cookie(response, token)
    return response


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    authorization: str | None = Header(None, alias="Authorization"),
    access_token: str | None = Cookie(None, alias=TOKEN_COOKIE_NAME),
    db: AsyncSession = Depends(get_database),
):
    """退出登录：删掉库里的 token 行 + 清 cookie。

    刻意**不要求**已登录：带着过期/无效凭证来退出也应该成功返回，
    否则前端会卡在 401 里、清不干净本地状态。
    """
    token = token_from_request(authorization, access_token)
    if token:
        await users.delete_token(db, token)
    response = success_response(message="已退出登录")
    clear_token_cookie(response)
    return response


@router.get(
    "/me",
    response_model=ApiResponse[UserInfoResponse],
    responses=documented_errors(401, 403),
)
async def get_user_info(user: User = Depends(get_current_user)):
    return success_response(data=UserInfoResponse.model_validate(user), message="获取用户信息成功")


async def _update_current_user(
    user_data: UserUpdateRequest, user: User, db: AsyncSession
):
    updated = await update_user(db, user.username, user_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return success_response(data=UserInfoResponse.model_validate(updated), message="更新用户信息成功")


@router.patch(
    "/me",
    response_model=ApiResponse[UserInfoResponse],
    responses=USER_ERRORS,
)
async def update_current_user(
    user_data: UserUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_database)
):
    return await _update_current_user(user_data, user, db)


@router.patch("", include_in_schema=False, deprecated=True)
async def update_current_user_legacy(
    user_data: UserUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_database)
):
    """兼容旧客户端的临时别名，新代码统一使用 PATCH /api/user/me。"""
    return await _update_current_user(user_data, user, db)


@router.put("/password", response_model=ApiResponse[None], responses=USER_ERRORS)
async def update_password(
    password_data: UserChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database),
):
    # 防止拿着已泄露的 token 反复试旧密码
    await enforce(f"pwd:{user.id}", 5, 60, "操作过于频繁，请 1 分钟后再试")
    res_change_pwd = await users.change_password(db, user, password_data.old_password, password_data.new_password)
    if not res_change_pwd:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="修改密码失败，请稍后再试")
    return success_response(message="修改密码成功")
