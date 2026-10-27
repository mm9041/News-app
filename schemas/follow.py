"""关注的请求模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FollowRequest(BaseModel):
    target_type: Literal["user", "category"] = Field(alias="targetType", description="关注类型")
    target_id: int = Field(..., ge=1, alias="targetId", description="目标ID")

    model_config = ConfigDict(populate_by_name=True)
