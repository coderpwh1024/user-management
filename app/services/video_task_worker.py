"""视频分析任务的受控线程池调度器。"""
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)
_executor = ThreadPoolExecutor(
    max_workers=settings.video_task_worker_count,
    thread_name_prefix="video-analysis",
)


def submit_video_analysis(task_id: str) -> None:
    """将任务投递至固定大小线程池，避免请求线程被三秒模拟任务阻塞。"""
    from app.crud.video_task import process_video_task

    _executor.submit(process_video_task, task_id)
    logger.info("视频分析任务已投递线程池: task_id=%s", task_id)


def shutdown_video_task_worker() -> None:
    """停止线程池并等待已开始的任务结束。"""
    _executor.shutdown(wait=True, cancel_futures=False)
