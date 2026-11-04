import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.comment import NewsComment
from models.users import User, UserToken
from schemas.users import UserRegisterRequest, UserUpdateRequest
from utils import security


def hash_token(token: str) -> str:
    """令牌入库前先哈希。

    库里的值一旦泄露（备份外流、误导库、SQL 注入），明文 token 等于直接把
    所有人的账号交出去 —— 攻击者拿它就能冒充任意用户，而且有效期还有 7 天。
    token 本身是高熵随机串，不需要加盐或慢哈希，SHA-256 足够且开销可忽略。
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_user_by_username(db: AsyncSession, username: str):
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_data: UserRegisterRequest):
    user = User(username=user_data.username, password=security.get_hash_password(user_data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_token(db: AsyncSession, user_id: int):
    """生成新令牌，返回**明文**（只此一次），库里只留哈希。

    secrets.token_urlsafe(32) 约 256 bit 熵，比 uuid4 的 122 bit 更稳；
    每用户只保留一条，重新登录会让旧 token 立即失效（多端会互相顶掉）。
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)
    token_hash = hash_token(token)
    query = select(UserToken).where(UserToken.user_id == user_id)
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()
    if user_token:
        user_token.token = token_hash
        user_token.expires_at = expires_at
    else:
        user_token = UserToken(user_id=user_id, token=token_hash, expires_at=expires_at)
        db.add(user_token)
    await db.commit()
    await db.refresh(user_token)
    return token


async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not security.verify_password(password, user.password):
        return None
    return user


async def get_user_by_token(db: AsyncSession, token: str):
    """根据 token 查出对应的用户；token 不存在或已过期则返回 None。

    库里存的是 sha256 摘要，所以这里要先哈希再查 —— 明文 token 永远不落库。
    """
    query = select(UserToken).where(UserToken.token == hash_token(token))
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()
    if not db_token or db_token.expires_at < datetime.now():
        return None

    query = select(User).where(User.id == db_token.user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def delete_token(db: AsyncSession, token: str) -> bool:
    """退出登录：把这条 token 从库里删掉（同样先哈希再匹配）。

    只清 cookie 不删库记录的话，那串 token 还能用满 7 天 —— 退出登录就不算数。
    """
    result = await db.execute(delete(UserToken).where(UserToken.token == hash_token(token)))
    await db.commit()
    return result.rowcount > 0


async def update_user(db: AsyncSession, username: str, user_data: UserUpdateRequest):
    query = update(User).where(User.username == username).values(**user_data.model_dump(
        exclude_unset=True,
        exclude_none=True
    ))
    result = await db.execute(query)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(404, "用户不存在")
    updated_user = await get_user_by_username(db, username)
    return updated_user


async def list_users_for_admin(db: AsyncSession, keyword: str | None, skip: int, limit: int):
    """管理员看用户列表，每行带评论数。"""
    conditions = []
    if keyword and keyword.strip():
        kw = keyword.strip()
        conditions.append(
            User.username.contains(kw, autoescape=True)
            | User.nickname.contains(kw, autoescape=True)
        )

    total = (
        await db.execute(select(func.count(User.id)).where(*conditions))
    ).scalar_one()

    stmt = (
        select(User, func.count(NewsComment.id))
        .outerjoin(NewsComment, NewsComment.user_id == User.id)
        .where(*conditions)
        .group_by(User.id)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows], total


# 修改密码: 验证旧密码 → 新密码加密 → 修改密码
async def change_password(db: AsyncSession, user: User, old_password: str, new_password: str):
    if not security.verify_password(old_password, user.password):
        return False

    hashed_new_pwd = security.get_hash_password(new_password)
    user.password = hashed_new_pwd
    # 更新: 由SQLAlchemy真正接管这个 User 对象，确保可以 commit
    # 规避 session 过期或关闭导致的不能提交的问题
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return True
