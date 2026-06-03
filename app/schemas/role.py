"""角色相关的 Pydantic 数据模型（请求 / 响应）。"""
from datetime import datetime
from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import validate_role_code


class StatusEnum(IntEnum):
    """角色状态枚举。"""

    DISABLED = 0
    ENABLED = 1


class RoleCreate(BaseModel):
    """创建角色请求体。"""

    role_code: str = Field(..., min_length=2, max_length=64, description="角色编码（全局唯一）")
    role_name: str = Field(..., min_length=1, max_length=64, description="角色名称")
    status: StatusEnum = Field(default=StatusEnum.ENABLED, description="状态 0:停用 1:启用")
    create_by: Optional[str] = Field(None, max_length=64, description="创建人")

    @field_validator("role_code")
    @classmethod
    def _check_role_code(cls, v: str) -> str:
        return validate_role_code(v)


class RoleUpdate(BaseModel):
    """更新角色请求体（字段均可选，仅更新传入字段）。"""

    role_code: Optional[str] = Field(None, min_length=2, max_length=64, description="角色编码（全局唯一）")
    role_name: Optional[str] = Field(None, min_length=1, max_length=64, description="角色名称")
    status: Optional[StatusEnum] = Field(None, description="状态 0:停用 1:启用")
    update_by: Optional[str] = Field(None, max_length=64, description="更新人")

    @field_validator("role_code")
    @classmethod
    def _check_role_code(cls, v: Optional[str]) -> Optional[str]:
        return validate_role_code(v) if v is not None else v


class RoleOut(BaseModel):
    """角色响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role_code: str
    role_name: str
    status: int
    create_by: Optional[str]
    update_by: Optional[str]
    gmt_create: datetime
    gmt_modified: datetime


class RolePage(BaseModel):
    """角色分页响应体。"""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: list[RoleOut] = Field(default_factory=list, description="数据列表")
