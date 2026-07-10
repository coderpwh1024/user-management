"""视频分析任务相关的 Pydantic 请求与响应模型。"""
from datetime import datetime
from enum import Enum, IntEnum

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class VideoTaskStatusCode(IntEnum):
    """数据库任务状态枚举。"""

    PROCESSING = 0
    SUCCESS = 1
    FAILED = 2


class VideoTaskStatus(str, Enum):
    """API 任务状态枚举。"""

    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class VideoTaskCreate(BaseModel):
    """视频上传任务请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(
        ..., alias="deviceId", min_length=1, max_length=32, description="设备ID"
    )
    video_url: AnyHttpUrl = Field(
        ..., alias="videoUrl", max_length=2048, description="视频地址"
    )
    duration: int = Field(..., ge=1, le=86400, description="视频时长（秒）")


class VideoTaskUpdate(BaseModel):
    """视频任务更新模型（字段均可选，仅更新传入字段）。"""

    model_config = ConfigDict(populate_by_name=True)

    video_url: AnyHttpUrl | None = Field(
        None, alias="videoUrl", max_length=2048
    )
    duration: int | None = Field(None, ge=1, le=86400)
    status: VideoTaskStatusCode | None = None
    result_url: AnyHttpUrl | None = Field(
        None, alias="resultUrl", max_length=2048
    )


class VideoTaskOut(BaseModel):
    """视频任务响应体。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
    status: VideoTaskStatus
    result_url: str | None = Field(None, alias="resultUrl")
    create_time: datetime = Field(..., alias="createTime")


class VideoTaskPage(BaseModel):
    """视频任务分页响应体。"""

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    items: list[VideoTaskOut] = Field(default_factory=list, description="数据列表")


class VideoTaskUploadOut(BaseModel):
    """视频上传成功响应数据。"""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
