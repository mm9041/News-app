from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, ConfigDict

# bcrypt 只处理前 72 字节，且 5.0 起对超长输入直接抛错（不再静默截断）。
# 在 schema 层就拦掉，让它变成可读的 422，而不是走到 crud 里抛 ValueError 变成 500。
BCRYPT_MAX_BYTES = 72


def _check_bcrypt_bytes(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"密码过长：UTF-8 编码后 {len(raw)} 字节，上限 {BCRYPT_MAX_BYTES} 字节"
            "（一个汉字占 3 字节）"
        )
    return password


# 注意：max_length 数的是**字符**，中文密码 30 个字就是 90 字节，
# 所以字符长度之外还要单独校验字节数。
BcryptPassword = Annotated[str, AfterValidator(_check_bcrypt_bytes)]


class UserRegisterRequest(BaseModel):
    """注册请求。

    强度约束只加在这里：登录用的是另一个模型（见 `UserRequest`），
    否则 5 位的老密码会被 422 挡在登录页外面。
    """

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: BcryptPassword = Field(
        ..., min_length=6, max_length=72, description="密码"
    )


class UserRequest(BaseModel):
    """登录请求。

    ⚠️ 刻意**不加** min_length：
    - 用户名/密码长度不合规属于「凭证不对」，应该由 authenticate_user 返回 401；
    - 种子账号 admin/admin 只有 5 位密码，加 min_length=6 会直接把它锁死。
    只挡住超长输入（否则 bcrypt 抛错会变成 500）。
    """

    username: str = Field(..., max_length=50, description="用户名")
    password: BcryptPassword = Field(..., max_length=72, description="密码")


# user_info 对应的类：基础类 + Info 类（id、用户名）
class UserInfoBase(BaseModel):
    """
    用户信息基础数据模型

    ⚠️ 这里的字段必须覆盖所有「前端需要回显」的列。
    漏掉一个（比如 phone）不会报错，只会表现为「保存成功但不生效」：
    库里写进去了，响应里没这个字段，前端拿到 undefined 就永远显示为空。
    """
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    gender: Optional[str] = Field(None, max_length=10, description="性别")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")


class UserInfoResponse(UserInfoBase):
    id: int
    username: str
    # 前端用它决定是否显示「管理后台」入口；真正的拦截在后端 get_current_admin
    is_admin: bool = Field(False, alias="isAdmin")
    model_config = ConfigDict(
        from_attributes=True,  # 允许从 ORM 对象属性中取值
        populate_by_name=True,
    )


class UserAuthResponse(BaseModel):
    token: str
    user_info: UserInfoResponse = Field(..., alias="userInfo")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )


# 更新用户信息的模型类
# 所有字段都可选：前端只提交改动的字段，未提交/显式传 null 都表示「不改」。
# 注意标注必须是 Optional[...] —— 写成 `nickname: str = None` 在 Pydantic v2 下
# 显式传 null 会被判成类型错误，直接 422（而且旧版 422 前端根本读不到原因）。
class UserUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    gender: Optional[Literal["male", "female", "unknown"]] = Field(None, description="性别")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")


class UserChangePasswordRequest(BaseModel):
    old_password: BcryptPassword = Field(..., alias="oldPassword", description="旧密码")
    new_password: BcryptPassword = Field(
        ..., min_length=6, max_length=72, alias="newPassword", description="新密码"
    )
