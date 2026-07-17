"""视频分析任务请求和响应模型。"""
from datetime import datetime
from decimal import Decimal
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import validate_video_url


class VideoTaskStatus(IntEnum):
    """视频任务内部状态枚举。"""

    PENDING = 0
    PROCESSING = 1
    SUCCESS = 2
    FAILED = 3


STATUS_NAME_MAP = {
    VideoTaskStatus.PENDING: "pending",
    VideoTaskStatus.PROCESSING: "processing",
    VideoTaskStatus.SUCCESS: "success",
    VideoTaskStatus.FAILED: "failed",
}


class VideoUploadCreate(BaseModel):
    """视频任务上报请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(..., alias="deviceId", min_length=1, max_length=32, description="设备唯一标识")
    video_url: str = Field(..., alias="videoUrl", min_length=1, max_length=2048, description="视频地址")
    duration: Decimal = Field(..., gt=0, max_digits=10, decimal_places=3, description="视频时长，单位秒")

    @field_validator("device_id")
    @classmethod
    def _strip_device_id(cls, value: str) -> str:
        """校验并规范设备标识。"""
        result = value.strip()
        if not result:
            raise ValueError("设备唯一标识不能为空")
        return result

    @field_validator("video_url")
    @classmethod
    def _check_video_url(cls, value: str) -> str:
        """校验视频地址。"""
        return validate_video_url(value)


class VideoUploadOut(BaseModel):
    """视频上报成功响应数据。"""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., serialization_alias="taskId", description="分析任务唯一标识")


class VideoStatusOut(BaseModel):
    """视频任务状态查询响应数据。"""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., serialization_alias="taskId")
    status: str
    result_url: str | None = Field(None, serialization_alias="resultUrl")
    create_time: datetime = Field(..., serialization_alias="createTime")
    failure_reason: str | None = Field(None, serialization_alias="failureReason")
