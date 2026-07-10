"""视频分析任务持久层与任务编排。

使用 MySQL 持久化任务状态，并通过 Redis Lua 脚本原子控制单设备并发任务数。
"""
import asyncio
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.exceptions import BusinessException
from app.core.logger import get_logger
from app.core.redis import get_redis_client
from app.core.redis import get_async_redis_client
from app.db.session import SessionLocal
from app.models.video_task import VideoTask
from app.schemas.video_task import (
    VideoTaskCreate,
    VideoTaskStatus,
    VideoTaskStatusCode,
    VideoTaskUpdate,
)

logger = get_logger(__name__)

CODE_NOT_FOUND = 40400
CODE_DEVICE_TASK_LIMIT = 429
CODE_TASK_CREATE_FAILED = 50001
CODE_REDIS_UNAVAILABLE = 50002
CODE_PERSISTENCE_QUEUE_FULL = 50003

_TASK_KEY_PREFIX = "video_task:data:"
_persistence_queue: queue.Queue[dict[str, object]] = queue.Queue(
    maxsize=settings.video_task_persistence_queue_size
)
_persistence_executor = ThreadPoolExecutor(
    max_workers=settings.video_task_persistence_workers,
    thread_name_prefix="video-persist",
)
_persistence_worker_started = False
_persistence_worker_lock = threading.Lock()

_RESERVE_SLOT_LUA = """
local key = KEYS[1]
local task_id = ARGV[1]
local task_limit = tonumber(ARGV[2])
local ttl_seconds = tonumber(ARGV[3])
if redis.call('SCARD', key) >= task_limit then
    return 0
end
redis.call('SADD', key, task_id)
redis.call('EXPIRE', key, ttl_seconds)
return 1
"""

_RELEASE_SLOT_LUA = """
local key = KEYS[1]
redis.call('SREM', key, ARGV[1])
if redis.call('SCARD', key) == 0 then
    redis.call('DEL', key)
end
return 1
"""


def _active_task_key(device_id: str) -> str:
    """生成设备活跃任务 Redis Key。"""
    return f"video_task:active:{device_id}"


def _task_data_key(task_id: str) -> str:
    """生成任务实时元数据 Redis Key。"""
    return f"{_TASK_KEY_PREFIX}{task_id}"


def _write_task_cache(redis_client: Redis, payload: dict[str, object]) -> None:
    """写入任务实时元数据，上传链路只依赖 Redis。"""
    try:
        pipeline = redis_client.pipeline(transaction=True)
        cache_mapping = {field: str(value) for field, value in payload.items()}
        pipeline.hset(
            _task_data_key(str(payload["task_id"])), mapping=cache_mapping  # type: ignore[arg-type]
        )
        pipeline.expire(
            _task_data_key(str(payload["task_id"])),
            settings.video_task_redis_ttl_seconds,
        )
        pipeline.execute()
    except RedisError as exc:
        logger.exception("任务实时元数据写入失败: task_id=%s", payload["task_id"])
        raise BusinessException("任务服务暂不可用", CODE_REDIS_UNAVAILABLE) from exc


def _update_task_cache(
    redis_client: Redis,
    task_id: str,
    status: VideoTaskStatus,
    result_url: str | None = None,
) -> None:
    """更新 Redis 中的实时任务状态。"""
    mapping: dict[str, str] = {"status": status.value}
    if result_url is not None:
        mapping["result_url"] = result_url
    else:
        mapping["result_url"] = ""
    try:
        redis_client.hset(  # type: ignore[arg-type]
            _task_data_key(task_id), mapping=mapping  # type: ignore[arg-type]
        )
        redis_client.expire(
            _task_data_key(task_id), settings.video_task_redis_ttl_seconds
        )
    except RedisError as exc:
        logger.exception("任务实时状态更新失败: task_id=%s", task_id)
        raise BusinessException("任务服务暂不可用", CODE_REDIS_UNAVAILABLE) from exc


def _start_persistence_worker() -> None:
    """启动单个有界持久化分发线程。"""
    global _persistence_worker_started
    with _persistence_worker_lock:
        if _persistence_worker_started:
            return
        thread = threading.Thread(
            target=_persistence_dispatch_loop,
            name="video-persist-dispatcher",
            daemon=True,
        )
        thread.start()
        _persistence_worker_started = True


def _enqueue_persistence(payload: dict[str, object]) -> None:
    """将 MySQL 写入放入有界队列，避免请求线程等待数据库连接。"""
    _start_persistence_worker()
    try:
        _persistence_queue.put_nowait(payload)
    except queue.Full as exc:
        logger.error("视频任务持久化队列已满: task_id=%s", payload["task_id"])
        raise BusinessException("任务写入队列繁忙，请稍后重试", CODE_PERSISTENCE_QUEUE_FULL) from exc


def _persistence_dispatch_loop() -> None:
    """分发持久化任务到受控 MySQL 线程池。"""
    while True:
        payload = _persistence_queue.get()
        try:
            _persistence_executor.submit(_persist_payload, payload)
        except RuntimeError:
            logger.exception("视频任务持久化线程池不可用: task_id=%s", payload["task_id"])
        finally:
            _persistence_queue.task_done()


def _persist_payload(payload: dict[str, object]) -> None:
    """在线程池中写入 MySQL，失败时重试并回写 Redis failed。"""
    db = SessionLocal()
    try:
        operation = str(payload["operation"])
        task_id = str(payload["task_id"])
        for attempt in range(3):
            try:
                if operation == "create":
                    task = _get_active_by_task_id(db, task_id)
                    if task is None:
                        task = VideoTask(
                            task_id=task_id,
                            device_id=str(payload["device_id"]),
                            video_url=str(payload["video_url"]),
                            duration=int(str(payload["duration"])),
                            task_status=int(VideoTaskStatusCode.PROCESSING),
                        )
                        db.add(task)
                else:
                    task = _get_active_by_task_id(db, task_id)
                    if task is not None:
                        task.task_status = int(str(payload["task_status"]))
                        task.result_url = str(payload.get("result_url") or "") or None
                db.commit()
                return
            except SQLAlchemyError:
                db.rollback()
                if attempt == 2:
                    raise
                # 连接耗尽时退避，避免持久化线程持续冲击 MySQL。
                import time

                time.sleep(0.1 * (attempt + 1))
    except Exception:
        logger.exception("视频任务 MySQL 异步持久化失败: task_id=%s", payload["task_id"])
        try:
            client = get_redis_client()
            _update_task_cache(client, str(payload["task_id"]), VideoTaskStatus.FAILED)
        except Exception:
            logger.exception("视频任务失败状态回写失败: task_id=%s", payload["task_id"])
    finally:
        db.close()


def _reserve_device_slot(redis_client: Redis, device_id: str, task_id: str) -> None:
    """原子占用单设备任务槽位。

    :raises BusinessException: Redis 不可用或设备并发任务达到上限。
    """
    try:
        reserved = redis_client.eval(
            _RESERVE_SLOT_LUA,
            1,
            _active_task_key(device_id),
            task_id,
            settings.video_task_device_limit,
            settings.video_task_slot_ttl_seconds,
        )
    except RedisError as exc:
        logger.exception("Redis 任务槽位占用失败: device_id=%s", device_id)
        raise BusinessException("任务服务暂不可用", CODE_REDIS_UNAVAILABLE) from exc

    if int(reserved) != 1:
        logger.warning("设备并发任务超限: device_id=%s", device_id)
        raise BusinessException(
            f"单设备同时最多 {settings.video_task_device_limit} 个任务",
            CODE_DEVICE_TASK_LIMIT,
        )


def _release_device_slot(redis_client: Redis, device_id: str, task_id: str) -> None:
    """释放单设备任务槽位，失败时等待 TTL 自动回收。"""
    try:
        redis_client.eval(
            _RELEASE_SLOT_LUA,
            1,
            _active_task_key(device_id),
            task_id,
        )
    except RedisError:
        logger.exception(
            "Redis 任务槽位释放失败: device_id=%s, task_id=%s",
            device_id,
            task_id,
        )


def _get_active_by_task_id(db: Session, task_id: str) -> VideoTask | None:
    """按任务 ID 查询未删除任务。"""
    stmt = select(VideoTask).where(
        VideoTask.task_id == task_id,
        VideoTask.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_video_task(db: Session, task_id: str) -> VideoTask:
    """查询视频任务，不存在时抛出业务异常。"""
    task = _get_active_by_task_id(db, task_id)
    if task is None:
        logger.info("视频任务不存在: task_id=%s", task_id)
        raise BusinessException("视频任务不存在", CODE_NOT_FOUND)
    return task


def create_video_task_fast(
    data: VideoTaskCreate,
    redis_client: Redis | None = None,
) -> tuple[str, str]:
    """快速创建任务。

    先将任务元数据写入 Redis，再把 MySQL 持久化放入有界线程池队列，
    从而避免上传请求同步等待 MySQL 连接和事务提交。
    """
    task_id = uuid4().hex
    client = redis_client or get_redis_client()
    _reserve_device_slot(client, data.device_id, task_id)
    payload: dict[str, object] = {
        "task_id": task_id,
        "device_id": data.device_id,
        "video_url": str(data.video_url),
        "duration": data.duration,
        "status": VideoTaskStatus.PROCESSING.value,
        "result_url": "",
        "create_time": datetime.now().isoformat(),
    }
    try:
        _write_task_cache(client, payload)
        _enqueue_persistence({"operation": "create", **payload})
    except BusinessException:
        _release_device_slot(client, data.device_id, task_id)
        try:
            client.delete(_task_data_key(task_id))
        except RedisError:
            logger.exception("清理任务实时元数据失败: task_id=%s", task_id)
        raise

    logger.debug("快速创建视频任务成功: task_id=%s, device_id=%s", task_id, data.device_id)
    return task_id, data.device_id


async def _reserve_device_slot_async(
    redis_client: AsyncRedis, device_id: str, task_id: str
) -> None:
    """异步原子占用设备任务槽位。"""
    try:
        reserved = await redis_client.eval(
            _RESERVE_SLOT_LUA,
            1,
            _active_task_key(device_id),
            task_id,
            settings.video_task_device_limit,
            settings.video_task_slot_ttl_seconds,
        )
    except RedisError as exc:
        logger.exception("异步 Redis 任务槽位占用失败: device_id=%s", device_id)
        raise BusinessException("任务服务暂不可用", CODE_REDIS_UNAVAILABLE) from exc
    if int(reserved) != 1:
        raise BusinessException(
            f"单设备同时最多 {settings.video_task_device_limit} 个任务",
            CODE_DEVICE_TASK_LIMIT,
        )


async def _write_task_cache_async(
    redis_client: AsyncRedis, payload: dict[str, object]
) -> None:
    """异步写入任务实时元数据。"""
    try:
        mapping = {field: str(value) for field, value in payload.items()}
        pipeline = redis_client.pipeline(transaction=True)
        await pipeline.hset(  # type: ignore[arg-type]
            _task_data_key(str(payload["task_id"])), mapping=mapping  # type: ignore[arg-type]
        )
        await pipeline.expire(
            _task_data_key(str(payload["task_id"])),
            settings.video_task_redis_ttl_seconds,
        )
        await pipeline.execute()
    except RedisError as exc:
        raise BusinessException("任务服务暂不可用", CODE_REDIS_UNAVAILABLE) from exc


async def create_video_task_fast_async(data: VideoTaskCreate) -> tuple[str, str]:
    """异步快速创建任务，完全避免占用 FastAPI 同步线程池。"""
    task_id = uuid4().hex
    client = await get_async_redis_client()
    await _reserve_device_slot_async(client, data.device_id, task_id)
    payload: dict[str, object] = {
        "task_id": task_id,
        "device_id": data.device_id,
        "video_url": str(data.video_url),
        "duration": data.duration,
        "status": VideoTaskStatus.PROCESSING.value,
        "result_url": "",
        "create_time": datetime.now().isoformat(),
    }
    try:
        await _write_task_cache_async(client, payload)
        _enqueue_persistence({"operation": "create", **payload})
    except Exception:
        try:
            await client.eval(
                _RELEASE_SLOT_LUA, 1, _active_task_key(data.device_id), task_id
            )
            await client.delete(_task_data_key(task_id))
        except RedisError:
            logger.exception("异步任务资源清理失败: task_id=%s", task_id)
        raise
    return task_id, data.device_id


def get_video_task_realtime(
    task_id: str,
    redis_client: Redis | None = None,
) -> dict[str, str | None]:
    """优先从 Redis 查询实时任务，缓存未命中时回源 MySQL。"""
    client = redis_client or get_redis_client()
    try:
        cached = client.hgetall(_task_data_key(task_id))
    except RedisError:
        cached = {}

    if cached:
        return {
            "task_id": str(cached["task_id"]),
            "status": str(cached["status"]),
            "result_url": str(cached.get("result_url") or "") or None,
            "create_time": str(cached["create_time"]),
        }

    db = SessionLocal()
    try:
        task = get_video_task(db, task_id)
        return {
            "task_id": task.task_id,
            "status": to_api_status(task.task_status).value,
            "result_url": task.result_url,
            "create_time": task.gmt_create.isoformat(),
        }
    finally:
        db.close()


async def get_video_task_realtime_async(task_id: str) -> dict[str, str | None]:
    """异步从 Redis 查询实时任务，缓存未命中时在线程中回源 MySQL。"""
    client = await get_async_redis_client()
    try:
        cached = await client.hgetall(_task_data_key(task_id))
    except RedisError:
        cached = {}
    if cached:
        return {
            "task_id": str(cached["task_id"]),
            "status": str(cached["status"]),
            "result_url": str(cached.get("result_url") or "") or None,
            "create_time": str(cached["create_time"]),
        }
    return await asyncio.to_thread(get_video_task_realtime, task_id)


def list_video_tasks(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    device_id: str | None = None,
    task_status: int | None = None,
) -> tuple[list[VideoTask], int]:
    """分页查询未删除视频任务，支持设备和状态精确过滤。"""
    conditions = [VideoTask.is_deleted == 0]
    if device_id:
        conditions.append(VideoTask.device_id == device_id)
    if task_status is not None:
        conditions.append(VideoTask.task_status == task_status)

    total = db.execute(
        select(func.count()).select_from(VideoTask).where(*conditions)
    ).scalar_one()
    stmt = (
        select(VideoTask)
        .where(*conditions)
        .order_by(VideoTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.execute(stmt).scalars().all()), total


def create_video_task(
    db: Session,
    data: VideoTaskCreate,
    redis_client: Redis | None = None,
) -> VideoTask:
    """创建视频分析任务，并原子占用设备并发槽位。"""
    task_id = uuid4().hex
    client = redis_client or get_redis_client()
    _reserve_device_slot(client, data.device_id, task_id)

    task = VideoTask(
        task_id=task_id,
        device_id=data.device_id,
        video_url=str(data.video_url),
        duration=data.duration,
        task_status=int(VideoTaskStatusCode.PROCESSING),
    )
    try:
        db.add(task)
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        _release_device_slot(client, data.device_id, task_id)
        logger.exception("创建视频任务失败: task_id=%s", task_id)
        raise BusinessException("创建视频任务失败", CODE_TASK_CREATE_FAILED) from exc

    logger.info(
        "创建视频任务成功: task_id=%s, device_id=%s", task_id, data.device_id
    )
    return task


def update_video_task(db: Session, task_id: str, data: VideoTaskUpdate) -> VideoTask:
    """局部更新视频任务，仅更新传入的非空字段。"""
    task = get_video_task(db, task_id)
    update_fields = data.model_dump(exclude_unset=True, exclude_none=True)
    field_mapping = {"status": "task_status"}

    for field, value in update_fields.items():
        target_field = field_mapping.get(field, field)
        if field in {"video_url", "result_url"}:
            value = str(value)
        if field == "status":
            value = int(value)
        setattr(task, target_field, value)

    db.commit()
    db.refresh(task)
    logger.info("更新视频任务成功: task_id=%s", task_id)
    return task


def delete_video_task(db: Session, task_id: str) -> None:
    """逻辑删除视频任务。"""
    task = get_video_task(db, task_id)
    task.is_deleted = 1
    db.commit()
    logger.info("逻辑删除视频任务成功: task_id=%s", task_id)


def to_api_status(task_status: int) -> VideoTaskStatus:
    """将数据库状态码转换为 API 状态文本。"""
    mapping = {
        VideoTaskStatusCode.PROCESSING: VideoTaskStatus.PROCESSING,
        VideoTaskStatusCode.SUCCESS: VideoTaskStatus.SUCCESS,
        VideoTaskStatusCode.FAILED: VideoTaskStatus.FAILED,
    }
    try:
        return mapping[VideoTaskStatusCode(task_status)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"未知任务状态: {task_status}") from exc


def _build_result_url(task_id: str) -> str:
    """生成模拟分析结果地址。"""
    return f"{settings.video_task_result_base_url.rstrip('/')}/{task_id}.json"


def _finish_analysis(task_id: str) -> None:
    """在线程池中完成数据库状态更新，并处理失败标记。"""
    db = SessionLocal()
    try:
        task = get_video_task(db, task_id)
        task.result_url = _build_result_url(task_id)
        task.task_status = int(VideoTaskStatusCode.SUCCESS)
        db.commit()
        logger.info("视频分析成功: task_id=%s", task_id)
    except Exception:
        db.rollback()
        logger.exception("视频分析失败: task_id=%s", task_id)
        try:
            failed_task = _get_active_by_task_id(db, task_id)
            if failed_task is not None:
                failed_task.task_status = int(VideoTaskStatusCode.FAILED)
                failed_task.result_url = None
                db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("视频任务失败状态回写失败: task_id=%s", task_id)
    finally:
        db.close()


def _finish_analysis_fast(task_id: str, redis_client: Redis) -> None:
    """快速链路仅更新 Redis，并异步排队 MySQL 状态更新。"""
    cached = redis_client.hgetall(_task_data_key(task_id))
    if not cached or cached.get("status") == VideoTaskStatus.FAILED.value:
        return
    result_url = _build_result_url(task_id)
    _update_task_cache(redis_client, task_id, VideoTaskStatus.SUCCESS, result_url)
    _enqueue_persistence(
        {
            "operation": "update",
            "task_id": task_id,
            "task_status": int(VideoTaskStatusCode.SUCCESS),
            "result_url": result_url,
        }
    )
    logger.info("视频分析成功（Redis 快速链路）: task_id=%s", task_id)


async def _update_task_cache_async(
    redis_client: AsyncRedis,
    task_id: str,
    status: VideoTaskStatus,
    result_url: str | None = None,
) -> None:
    """异步更新任务状态缓存。"""
    mapping = {"status": status.value, "result_url": result_url or ""}
    await redis_client.hset(  # type: ignore[arg-type]
        _task_data_key(task_id), mapping=mapping  # type: ignore[arg-type]
    )
    await redis_client.expire(
        _task_data_key(task_id), settings.video_task_redis_ttl_seconds
    )


async def analyze_video_task_async(task_id: str, device_id: str) -> None:
    """异步分析任务，不使用同步 Redis 或数据库连接。"""
    client = await get_async_redis_client()
    try:
        await asyncio.sleep(settings.video_task_analysis_delay_seconds)
        cached = await client.hgetall(_task_data_key(task_id))
        if not cached or cached.get("status") == VideoTaskStatus.FAILED.value:
            return
        result_url = _build_result_url(task_id)
        await _update_task_cache_async(
            client, task_id, VideoTaskStatus.SUCCESS, result_url
        )
        _enqueue_persistence(
            {
                "operation": "update",
                "task_id": task_id,
                "task_status": int(VideoTaskStatusCode.SUCCESS),
                "result_url": result_url,
            }
        )
    except Exception:
        logger.exception("视频分析异步链路失败: task_id=%s", task_id)
        try:
            await _update_task_cache_async(client, task_id, VideoTaskStatus.FAILED)
            _enqueue_persistence(
                {
                    "operation": "update",
                    "task_id": task_id,
                    "task_status": int(VideoTaskStatusCode.FAILED),
                    "result_url": "",
                }
            )
        except Exception:
            logger.exception("异步分析失败状态回写失败: task_id=%s", task_id)
    finally:
        try:
            await client.eval(
                _RELEASE_SLOT_LUA, 1, _active_task_key(device_id), task_id
            )
        except RedisError:
            logger.exception("异步任务槽位释放失败: task_id=%s", task_id)


async def analyze_video_task(
    task_id: str,
    device_id: str,
    redis_client: Redis | None = None,
) -> None:
    """异步模拟视频分析，并在结束后释放设备并发槽位。"""
    client = redis_client or get_redis_client()
    try:
        await asyncio.sleep(settings.video_task_analysis_delay_seconds)
        try:
            cached = client.hgetall(_task_data_key(task_id))
        except RedisError:
            cached = {}
        if cached:
            await run_in_threadpool(_finish_analysis_fast, task_id, client)
        else:
            # 兼容同步 CRUD 调用及历史任务。
            await run_in_threadpool(_finish_analysis, task_id)
    except Exception:
        logger.exception("视频分析快速链路失败: task_id=%s", task_id)
        try:
            _update_task_cache(client, task_id, VideoTaskStatus.FAILED)
            _enqueue_persistence(
                {
                    "operation": "update",
                    "task_id": task_id,
                    "task_status": int(VideoTaskStatusCode.FAILED),
                    "result_url": "",
                }
            )
        except Exception:
            logger.exception("视频分析失败状态排队失败: task_id=%s", task_id)
    finally:
        _release_device_slot(client, device_id, task_id)
