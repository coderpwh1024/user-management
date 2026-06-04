"""视频异步上传任务相关的 Pydantic 数据模型（请求 / 响应）。

注意命名映射：DB 列与 ORM 字段采用下划线（``task_id`` / ``video_url`` /
``gmt_create``），与项目既有 ``t_role`` / ``t_user`` 保持一致；
而对外 HTTP 接口的出入参一律使用驼峰（``taskId`` / ``videoUrl`` /
``resultUrl`` / ``createTime``），通过 Pydantic ``alias`` 完成两边映射。
"""
from datetime import datetime
from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import validate_video_url


class VideoStatusEnum(IntEnum):
    """视频任务状态枚举。"""

    PROCESSING = 0  # 处理中（在途）
    SUCCESS = 1     # 上传 / 分析成功
    FAILED = 2      # 上传 / 分析失败


class VideoUploadRequest(BaseModel):
    """视频上传请求体（入参驼峰：deviceId / videoUrl / duration）。"""

    # populate_by_name=True 同时兼容驼峰 alias 与下划线字段名两种入参写法
    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(
        ..., alias="deviceId", min_length=1, max_length=64, description="设备ID"
    )
    video_url: str = Field(
        ..., alias="videoUrl", min_length=1, max_length=512, description="原始视频链接"
    )
    duration: Optional[int] = Field(
        None, ge=0, le=86400, description="视频时长(秒)"
    )

    @field_validator("video_url")
    @classmethod
    def _check_video_url(cls, v: str) -> str:
        return validate_video_url(v)


class VideoUploadOut(BaseModel):
    """视频上传响应体（出参含 taskId）。"""

    task_id: str = Field(..., serialization_alias="taskId", description="任务ID（UUID）")


class VideoStatusOut(BaseModel):
    """视频任务状态查询响应体。"""

    task_id: str = Field(..., serialization_alias="taskId", description="任务ID（UUID）")
    status: int = Field(..., description="任务状态 0:处理中 1:成功 2:失败")
    result_url: Optional[str] = Field(
        None, serialization_alias="resultUrl", description="分析结果链接"
    )
    device_id: str = Field(..., serialization_alias="deviceId", description="设备ID")
    duration: Optional[int] = Field(None, description="视频时长(秒)")
    error_msg: Optional[str] = Field(
        None, serialization_alias="errorMsg", description="失败原因"
    )
    create_time: datetime = Field(
        ..., serialization_alias="createTime", description="创建时间"
    )
    update_time: datetime = Field(
        ..., serialization_alias="updateTime", description="更新时间"
    )
