"""压测调优版启动入口（仅用于压测对比，不修改生产代码）。

相对基线的两处调优：
1. **默认线程池**：``asyncio.to_thread`` 默认 executor 仅约 ``min(32, cpu+4)`` 个线程，
   是同步 DB 写在高并发下的瓶颈。这里在启动时替换为更大的 ThreadPoolExecutor。
2. **DB 连接池**：通过环境变量 ``DB_POOL_SIZE`` / ``DB_MAX_OVERFLOW`` 放大
   （由 pydantic-settings 覆盖 Settings，无需改代码）。

启动示例：
    DB_POOL_SIZE=64 DB_MAX_OVERFLOW=64 LOG_LEVEL=WARNING APP_DEBUG=false \\
      .venv/bin/python -m uvicorn loadtest.serve_tuned:app \\
      --host 127.0.0.1 --port 9003 --no-access-log --log-level warning
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.logger import get_logger
from app.main import app

logger = get_logger(__name__)

# 调优后的线程池大小（与放大的 DB 连接池相匹配）
_EXECUTOR_WORKERS = 64


@app.on_event("startup")
async def _tune_executor() -> None:
    """启动时放大事件循环默认线程池，缓解同步 DB 写排队。"""
    loop = asyncio.get_running_loop()
    loop.set_default_executor(
        ThreadPoolExecutor(
            max_workers=_EXECUTOR_WORKERS, thread_name_prefix="loadtest-db"
        )
    )
    logger.warning("[压测调优] 默认线程池 max_workers=%s", _EXECUTOR_WORKERS)
