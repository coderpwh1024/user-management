"""视频分析任务持久层及异步处理逻辑。"""
import time
from datetime import datetime
from typing import TypedDict
from uuid import uuid4

from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.logger import get_logger
from app.core.redis import get_redis_client
from app.db.session import SessionLocal
from app.models.video_task import VideoTask
from app.schemas.video_task import STATUS_NAME_MAP, VideoTaskStatus, VideoUploadCreate

logger = get_logger(__name__)

CODE_NOT_FOUND = 40400
CODE_DEVICE_TASK_LIMIT = 429
CODE_REDIS_UNAVAILABLE = 50301
DEVICE_RUNNING_LIMIT = 2
DEVICE_COUNTER_TTL_SECONDS = 3600

_ACQUIRE_DEVICE_SLOT_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current >= tonumber(ARGV[1]) then return 0 end
current = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return current
"""
_RELEASE_DEVICE_SLOT_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
if current <= 1 then redis.call('DEL', KEYS[1]); return 0 end
return redis.call('DECR', KEYS[1])
"""


class VideoTaskStatusData(TypedDict):
    """视频状态查询的内部数据结构。"""

    task_id: str
    status: str
    result_url: str | None
    create_time: datetime
    failure_reason: str | None


def _device_slot_key(device_id: str) -> str:
    """生成单设备执行任务计数器键。"""
    return f"video_task:device:{device_id}:running"


def _acquire_device_slot(device_id: str) -> None:
    """用 Redis Lua 脚本原子占用设备任务槽位。"""
    try:
        result = get_redis_client().eval(
            _ACQUIRE_DEVICE_SLOT_LUA, 1, _device_slot_key(device_id),
            DEVICE_RUNNING_LIMIT, DEVICE_COUNTER_TTL_SECONDS,
        )
    except RedisError as exc:
        logger.warning("Redis 不可用，拒绝创建视频任务: device_id=%s, error=%s", device_id, exc)
        raise BusinessException("任务限流服务暂不可用", CODE_REDIS_UNAVAILABLE) from exc
    if int(result) == 0:
        logger.warning("设备执行任务数达到上限: device_id=%s", device_id)
        raise BusinessException("单台设备同时最多允许 2 个正在执行的任务", CODE_DEVICE_TASK_LIMIT)


def _release_device_slot(device_id: str) -> None:
    """释放设备任务槽位；Redis 短暂故障由过期时间兜底。"""
    try:
        get_redis_client().eval(_RELEASE_DEVICE_SLOT_LUA, 1, _device_slot_key(device_id))
    except RedisError as exc:
        logger.warning("释放设备任务槽位失败，等待 TTL 自动恢复: device_id=%s, error=%s", device_id, exc)


def create_video_task(db: Session, data: VideoUploadCreate) -> VideoTask:
    """创建等待处理的视频任务并原子执行单设备限流。"""
    _acquire_device_slot(data.device_id)
    task = VideoTask(
        task_id=uuid4().hex,
        device_id=data.device_id,
        video_url=data.video_url,
        duration=data.duration,
        task_status=int(VideoTaskStatus.PENDING),
    )
    try:
        db.add(task)
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        _release_device_slot(data.device_id)
        logger.exception("创建视频任务失败: device_id=%s", data.device_id)
        raise
    logger.info("创建视频任务成功: task_id=%s, device_id=%s", task.task_id, task.device_id)
    return task


def create_and_submit_video_task(db: Session, data: VideoUploadCreate) -> VideoTask:
    """创建任务并投递异步分析；投递失败时保证状态和限流槽位得到恢复。"""
    task = create_video_task(db, data)
    try:
        from app.services.video_task_worker import submit_video_analysis

        submit_video_analysis(task.task_id)
    except RuntimeError as exc:
        task.task_status = int(VideoTaskStatus.FAILED)
        task.failure_reason = "分析任务调度失败"
        db.commit()
        _release_device_slot(task.device_id)
        logger.exception("视频任务投递失败: task_id=%s", task.task_id)
        raise BusinessException("分析任务调度失败", 50000) from exc
    return task


def get_video_task(db: Session, task_id: str) -> VideoTask:
    """查询未逻辑删除的视频任务。"""
    task = db.execute(select(VideoTask).where(VideoTask.task_id == task_id, VideoTask.is_deleted == 0)).scalar_one_or_none()
    if task is None:
        logger.info("视频任务不存在: task_id=%s", task_id)
        raise BusinessException("视频任务不存在", CODE_NOT_FOUND)
    return task


def get_video_status(db: Session, task_id: str) -> VideoTaskStatusData:
    """查询并转换为对外状态值。"""
    task = get_video_task(db, task_id)
    return {
        "task_id": task.task_id,
        "status": STATUS_NAME_MAP[VideoTaskStatus(task.task_status)],
        "result_url": task.result_url,
        "create_time": task.gmt_create,
        "failure_reason": task.failure_reason,
    }


def process_video_task(task_id: str) -> None:
    """在线程池中模拟三秒分析，并持久化成功或失败状态。"""
    db = SessionLocal()
    device_id: str | None = None
    try:
        task = db.execute(select(VideoTask).where(VideoTask.task_id == task_id, VideoTask.is_deleted == 0)).scalar_one_or_none()
        if task is None:
            logger.warning("异步任务不存在或已删除: task_id=%s", task_id)
            return
        device_id = task.device_id
        task.task_status = int(VideoTaskStatus.PROCESSING)
        db.commit()
        logger.info("开始视频分析: task_id=%s", task_id)
        time.sleep(3)
        task.task_status = int(VideoTaskStatus.SUCCESS)
        task.result_url = f"{task.video_url}.result.json"
        task.failure_reason = None
        db.commit()
        logger.info("视频分析完成: task_id=%s", task_id)
    except Exception as exc:
        db.rollback()
        logger.exception("视频分析失败: task_id=%s", task_id)
        try:
            db.execute(
                update(VideoTask)
                .where(VideoTask.task_id == task_id, VideoTask.is_deleted == 0)
                .values(task_status=int(VideoTaskStatus.FAILED), failure_reason=str(exc)[:500])
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("写入视频任务失败状态失败: task_id=%s", task_id)
    finally:
        if device_id:
            _release_device_slot(device_id)
        db.close()
