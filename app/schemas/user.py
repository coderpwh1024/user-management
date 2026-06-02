"""用户相关的 Pydantic 数据模型（请求 / 响应）。"""
from datetime import datetime
from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import validate_id_card, validate_phone


class GenderEnum(IntEnum):
    """性别枚举。"""

    UNKNOWN = 0
    MALE = 1
    FEMALE = 2


class UserCreate(BaseModel):
    """创建用户请求体。"""

    name: str = Field(..., min_length=1, max_length=64, description="姓名")
    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")
    phone: str = Field(..., description="手机号")
    id_card: str = Field(..., description="身份证号")
    gender: GenderEnum = Field(default=GenderEnum.UNKNOWN, description="性别 0:未知 1:男 2:女")
    create_by: Optional[str] = Field(None, max_length=64, description="创建人")

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return validate_phone(v)

    @field_validator("id_card")
    @classmethod
    def _check_id_card(cls, v: str) -> str:
        return validate_id_card(v)


class UserUpdate(BaseModel):
    """更新用户请求体（字段均可选，仅更新传入字段）。"""

    name: Optional[str] = Field(None, min_length=1, max_length=64, description="姓名")
    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")
    phone: Optional[str] = Field(None, description="手机号")
    id_card: Optional[str] = Field(None, description="身份证号")
    gender: Optional[GenderEnum] = Field(None, description="性别 0:未知 1:男 2:女")
    update_by: Optional[str] = Field(None, max_length=64, description="更新人")

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone(v) if v is not None else v

    @field_validator("id_card")
    @classmethod
    def _check_id_card(cls, v: Optional[str]) -> Optional[str]:
        return validate_id_card(v) if v is not None else v


class UserOut(BaseModel):
    """用户响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: Optional[int]
    phone: str
    id_card: str
    gender: int
    create_by: Optional[str]
    update_by: Optional[str]
    create_date: datetime
    update_time: datetime


class UserPage(BaseModel):
    """用户分页响应体。"""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: list[UserOut] = Field(default_factory=list, description="数据列表")
