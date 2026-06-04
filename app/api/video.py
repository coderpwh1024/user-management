"""视频异步上传与任务查询接口路由。

提供两个接口（按需求约定使用 ``/api/video`` 前缀，非 RESTful 复数版本路径）：
- ``POST /api/video/upload``      —— 受理上传，立即返回 taskId（异步处理）；
- ``GET  /api/video/status/{task_id}`` —— 查询任务状态与结果。

路由层仅做参数接收与编排，业务逻辑在 service / crud 层。
"""
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.response import ApiResponse
from app.crud import video_task as video_crud
from app.db.session import get_db
from app.schemas.video_task import (
    VideoStatusOut,
    VideoUploadOut,
    VideoUploadRequest,
)
from app.services import video_task as video_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/video", tags=["视频任务"])


@router.post("/upload", summary="视频异步上传", response_model=ApiResponse[VideoUploadOut])
async def upload_video(payload: VideoUploadRequest) -> ApiResponse:
    """受理视频上传请求。

    入参：``deviceId`` / ``videoUrl`` / ``duration``；
    立即返回 ``data.taskId``，真正的上传与分析在后台异步进行。
    单设备在途任务超过上限时返回 code=429。
    """
    logger.info("请求视频上传: device_id=%s", payload.device_id)
    task_id = await video_service.submit_upload(
        payload.device_id, payload.video_url, payload.duration
    )
    return ApiResponse.ok(VideoUploadOut(task_id=task_id))


@router.get(
    "/status/{task_id}",
    summary="查询视频任务状态",
    response_model=ApiResponse[VideoStatusOut],
)
def get_video_status(
    task_id: str = Path(..., min_length=1, max_length=64, description="任务ID（UUID）"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """根据 taskId 查询任务状态、结果链接等信息。"""
    logger.info("请求查询视频任务状态: task_id=%s", task_id)
    task = video_crud.get_by_task_id(db, task_id)
    data = VideoStatusOut(
        task_id=task.task_id,
        status=task.status,
        result_url=task.result_url,
        device_id=task.device_id,
        duration=task.duration,
        error_msg=task.error_msg,
        create_time=task.gmt_create,
        update_time=task.gmt_modified,
    )
    return ApiResponse.ok(data)
