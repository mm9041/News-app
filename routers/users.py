from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_database
from crud import users
from crud.users import create_user, get_user_by_username, create_token, update_user
from models.users import User
from schemas.users import (
    UserRegisterRequest,
    UserRequest,
    UserAuthResponse,
    UserInfoResponse,
    UserUpdateRequest,
    UserChangePasswordRequest,
)
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


@router.post("/register")
async def register(user_data: UserRegisterRequest, request: Request, db: AsyncSession = Depends(get_database)):
    # 防批量注册：同一 IP 每分钟最多 5 个账号
    await enforce(f"register:{client_ip(request)}", 5, 60, "注册过于频繁，请 1 分钟后再试")
    if await get_user_by_username(db, user_data.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已存在")
    user = await create_user(db, user_data)
    token = await create_token(db, user.id)
    response_data = UserAuthResponse(token=token, userInfo=UserInfoResponse.model_validate(user))
    response = success_response(data=response_data, message="注册成功")
    # 同时下发 httpOnly cookie：浏览器后续请求自动带上，前端不用碰 token
    set_token_cookie(response, token)
    return response


@router.post("/login")
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
    response_data = UserAuthResponse(token=token, userInfo=UserInfoResponse.model_validate(user))
    response = success_response(data=response_data, message="登录成功")
    set_token_cookie(response, token)
    return response


@router.post("/logout")
async def logout(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        access_token: Optional[str] = Cookie(None, alias=TOKEN_COOKIE_NAME),
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


@router.get("/info")
async def get_user_info(user: User = Depends(get_current_user)):
    return success_response(data=UserInfoResponse.model_validate(user), message="获取用户信息成功")


@router.put("/update")
async def update_user_info(user_data: UserUpdateRequest, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_database)):
    user = await update_user(db, user.username, user_data)
    return success_response(data=UserInfoResponse.model_validate(user), message="更新用户信息成功")


@router.put("/password")
async def update_password(
        password_data: UserChangePasswordRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database)):
    # 防止拿着已泄露的 token 反复试旧密码
    await enforce(f"pwd:{user.id}", 5, 60, "操作过于频繁，请 1 分钟后再试")
    res_change_pwd = await users.change_password(db, user, password_data.old_password, password_data.new_password)
    if not res_change_pwd:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="修改密码失败，请稍后再试")
    return success_response(message="修改密码成功")
