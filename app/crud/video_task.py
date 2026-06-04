"""视频异步上传任务持久层（CRUD）。

封装对 ``t_video_task`` 表的数据库操作，统一处理逻辑删除（is_deleted）。
业务异常以 ``BusinessException`` 形式抛出。

并发限流：``count_active_by_device`` 统计单设备在途（status=处理中）任务数，
配合组合索引 ``idx_device_id_status``，由 service 层据此判断是否超限。
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.logger import get_logger
from app.models.video_task import VideoTask
from app.schemas.video_task import VideoStatusEnum

logger = get_logger(__name__)

# 业务错误码
CODE_NOT_FOUND = 40400          # 任务不存在
CODE_DEVICE_LIMIT = 429         # 单设备并发任务数超限（按需求约定 code=429）

# 单设备允许的最大在途任务数
MAX_ACTIVE_PER_DEVICE = 2


def count_active_by_device(db: Session, device_id: str) -> int:
    """统计某设备当前在途（处理中）的任务数量。

    :param device_id: 设备ID。
    :return: 处理中且未逻辑删除的任务数。
    """
    return db.execute(
        select(func.count())
        .select_from(VideoTask)
        .where(
            VideoTask.device_id == device_id,
            VideoTask.status == int(VideoStatusEnum.PROCESSING),
            VideoTask.is_deleted == 0,
        )
    ).scalar_one()


def create_task(
    db: Session,
    task_id: str,
    device_id: str,
    video_url: str,
    duration: Optional[int] = None,
) -> VideoTask:
    """创建一条处理中的视频任务记录。

    :param task_id: 调用方主动生成的 UUID。
    :return: 持久化后的任务实体。
    """
    task = VideoTask(
        task_id=task_id,
        device_id=device_id,
        video_url=video_url,
        duration=duration,
        status=int(VideoStatusEnum.PROCESSING),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    logger.info(
        "创建视频任务成功: task_id=%s, device_id=%s", task.task_id, task.device_id
    )
    return task


def get_by_task_id(db: Session, task_id: str) -> VideoTask:
    """根据 task_id 查询任务，不存在则抛业务异常。"""
    task = db.execute(
        select(VideoTask).where(
            VideoTask.task_id == task_id, VideoTask.is_deleted == 0
        )
    ).scalar_one_or_none()
    if task is None:
        logger.info("视频任务不存在: task_id=%s", task_id)
        raise BusinessException("任务不存在", CODE_NOT_FOUND)
    return task


def mark_success(db: Session, task_id: str, result_url: str) -> None:
    """将任务标记为成功，并写入分析结果链接。"""
    task = get_by_task_id(db, task_id)
    task.status = int(VideoStatusEnum.SUCCESS)
    task.result_url = result_url
    task.error_msg = None
    db.commit()
    logger.info("视频任务处理成功: task_id=%s", task_id)


def mark_failed(db: Session, task_id: str, error_msg: str) -> None:
    """将任务标记为失败，并记录失败原因。"""
    task = get_by_task_id(db, task_id)
    task.status = int(VideoStatusEnum.FAILED)
    task.error_msg = (error_msg or "")[:512]
    db.commit()
    logger.warning("视频任务处理失败: task_id=%s, reason=%s", task_id, task.error_msg)
