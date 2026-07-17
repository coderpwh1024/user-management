"""视频任务上报和状态查询接口。"""
from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.response import ApiResponse
from app.crud import video_task as video_task_crud
from app.db.session import get_db
from app.schemas.video_task import VideoStatusOut, VideoUploadCreate, VideoUploadOut

logger = get_logger(__name__)
router = APIRouter(prefix="/api/video", tags=["视频分析任务"])


@router.post("/upload", summary="视频任务上报", response_model=ApiResponse[VideoUploadOut])
def upload_video(payload: VideoUploadCreate, db: Session = Depends(get_db)) -> ApiResponse:
    """创建任务并异步投递模拟分析，不阻塞请求线程。"""
    task = video_task_crud.create_and_submit_video_task(db, payload)
    return ApiResponse.ok(VideoUploadOut(task_id=task.task_id))


@router.get("/status/{task_id}", summary="查询视频任务状态", response_model=ApiResponse[VideoStatusOut])
def get_video_status(
    task_id: str = Path(..., min_length=32, max_length=32, pattern="^[0-9a-f]{32}$", description="分析任务唯一标识"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """实时查询指定视频任务的执行状态。"""
    logger.info("请求查询视频任务状态: task_id=%s", task_id)
    return ApiResponse.ok(VideoStatusOut(**video_task_crud.get_video_status(db, task_id)))
