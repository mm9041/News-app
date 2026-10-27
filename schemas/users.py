from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class UserRequest(BaseModel):
    username: str
    password: str


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
    old_password: str = Field(..., alias="oldPassword", description="旧密码")
    new_password: str = Field(..., min_length=6, alias="newPassword", description="新密码")
