"""视频上传与任务状态查询接口。"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Path

from app.core.logger import get_logger
from app.core.response import ApiResponse
from app.crud import video_task as video_task_crud
from app.schemas.video_task import (
    VideoTaskCreate,
    VideoTaskOut,
    VideoTaskStatus,
    VideoTaskUploadOut,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/video", tags=["视频分析任务"])


@router.post(
    "/upload",
    summary="上传视频分析任务",
    response_model=ApiResponse[VideoTaskUploadOut],
)
async def upload_video(
    payload: VideoTaskCreate,
    background_tasks: BackgroundTasks,
) -> ApiResponse:
    """上报视频并异步触发分析。"""
    logger.debug("请求上传视频任务: device_id=%s", payload.device_id)
    task_id, device_id = await video_task_crud.create_video_task_fast_async(payload)
    background_tasks.add_task(
        video_task_crud.analyze_video_task_async,
        task_id,
        device_id,
    )
    return ApiResponse.ok(VideoTaskUploadOut(taskId=task_id))


@router.get(
    "/status/{task_id}",
    summary="查询视频分析任务状态",
    response_model=ApiResponse[VideoTaskOut],
)
async def get_video_status(
    task_id: str = Path(
        ..., min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$", description="任务ID"
    ),
) -> ApiResponse:
    """按任务 ID 实时查询分析状态。"""
    task = await video_task_crud.get_video_task_realtime_async(task_id)
    data = VideoTaskOut(
        taskId=str(task["task_id"]),
        status=VideoTaskStatus(str(task["status"])),
        resultUrl=task["result_url"],
        createTime=datetime.fromisoformat(str(task["create_time"])),
    )
    return ApiResponse.ok(data)
