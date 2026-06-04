"""视频异步上传 / 分析的业务编排层。

职责（介于 api 与 crud 之间的 service 层）：
1. 受理上传请求：单设备并发限流 + 生成 UUID + 落库一条「处理中」任务，立即返回 taskId；
2. 调度后台协程异步执行「上传 + 分析」（此处用 ``asyncio.sleep(3)`` 模拟耗时 IO）；
3. 处理完成后回写任务状态（成功 / 失败）。

设计要点
--------
- **异步不阻塞**：接口 ``async def`` 受理后立即返回，真正的上传分析交由
  ``asyncio.create_task`` 在后台事件循环执行，单进程可承载约 500 并发在途任务。
- **DB 不阻塞事件循环**：同步 SQLAlchemy 操作统一用 ``asyncio.to_thread`` 丢到线程池，
  且每次使用独立的 ``SessionLocal()`` 会话（请求级会话已随响应关闭，后台不可复用）。
- **并发限流（单设备最多 2 个在途任务）**：以「每设备一把 ``asyncio.Lock``」串行化
  「COUNT 在途数 + 插入」这对临界区操作，配合 DB 实时 COUNT 实现精确限流；
  单进程内严格不超限。多 worker 部署时仍以 DB COUNT 为准（可能存在极小竞态窗口，
  生产环境建议改用 Redis / 数据库分布式锁，详见 docs/API.md）。
"""
import asyncio
import uuid
from collections import defaultdict

from app.core.exceptions import BusinessException
from app.core.logger import get_logger
from app.crud import video_task as crud
from app.crud.video_task import CODE_DEVICE_LIMIT, MAX_ACTIVE_PER_DEVICE
from app.db.session import SessionLocal

logger = get_logger(__name__)

# 模拟上传 + 分析的耗时（秒）
_PROCESS_SECONDS = 3

# 每设备一把锁，串行化「计数 + 插入」临界区，保证单进程内精确限流。
# 仅在事件循环线程内同步访问该字典，无需额外加锁。
_device_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _create_task_sync(
    task_id: str, device_id: str, video_url: str, duration: int | None
) -> None:
    """同步执行：在线程池中完成「在途计数校验 + 落库」（独立会话）。"""
    db = SessionLocal()
    try:
        active = crud.count_active_by_device(db, device_id)
        if active >= MAX_ACTIVE_PER_DEVICE:
            logger.warning(
                "设备并发超限: device_id=%s, active=%s", device_id, active
            )
            raise BusinessException(
                f"设备在途任务数已达上限（{MAX_ACTIVE_PER_DEVICE}），请稍后再试",
                CODE_DEVICE_LIMIT,
            )
        crud.create_task(db, task_id, device_id, video_url, duration)
    finally:
        db.close()


def _mark_success_sync(task_id: str, result_url: str) -> None:
    """同步执行：标记任务成功（独立会话）。"""
    db = SessionLocal()
    try:
        crud.mark_success(db, task_id, result_url)
    finally:
        db.close()


def _mark_failed_sync(task_id: str, error_msg: str) -> None:
    """同步执行：标记任务失败（独立会话）。"""
    db = SessionLocal()
    try:
        crud.mark_failed(db, task_id, error_msg)
    finally:
        db.close()


async def _process(task_id: str) -> None:
    """后台协程：模拟视频上传 + 分析，完成后回写状态。"""
    try:
        # 模拟上传 + 分析耗时（非阻塞），真实场景替换为对象存储上传 / 模型推理调用
        await asyncio.sleep(_PROCESS_SECONDS)
        result_url = f"https://result.example.com/{task_id}.json"
        await asyncio.to_thread(_mark_success_sync, task_id, result_url)
    except Exception as exc:  # noqa: BLE001  后台任务需兜底，避免静默丢失
        logger.exception("视频任务后台处理异常: task_id=%s", task_id)
        try:
            await asyncio.to_thread(_mark_failed_sync, task_id, str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("回写失败状态亦异常: task_id=%s", task_id)


def schedule_processing(task_id: str) -> None:
    """调度后台处理协程。

    抽成独立函数便于单测替换（避免测试触发真实 3 秒后台任务）。
    """
    asyncio.create_task(_process(task_id))


async def submit_upload(
    device_id: str, video_url: str, duration: int | None
) -> str:
    """受理一次视频上传请求。

    :param device_id: 设备ID。
    :param video_url: 原始视频链接。
    :param duration: 视频时长(秒)，可空。
    :return: 主动生成的任务 ID（UUID）。
    :raises BusinessException: 单设备在途任务超限时抛出 code=429。
    """
    task_id = uuid.uuid4().hex
    lock = _device_locks[device_id]
    # 临界区：同设备的「计数 + 插入」串行化，杜绝并发下越过上限
    async with lock:
        await asyncio.to_thread(
            _create_task_sync, task_id, device_id, video_url, duration
        )

    logger.info("受理视频上传: task_id=%s, device_id=%s", task_id, device_id)
    # 落库成功后再调度后台分析
    schedule_processing(task_id)
    return task_id
