"""统一 API 响应封装。

所有接口返回统一结构：``{"code", "message", "data"}``，
便于前端统一处理。
"""
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应体。"""

    code: int = 0
    message: str = "success"
    data: Optional[T] = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        """构造成功响应。"""
        return cls(code=0, message=message, data=data)

    @classmethod
    def fail(cls, code: int, message: str, data: Any = None) -> "ApiResponse":
        """构造失败响应。"""
        return cls(code=code, message=message, data=data)
