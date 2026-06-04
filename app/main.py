"""应用入口。

创建 FastAPI 实例，注册路由、异常处理器及健康检查接口。
启动: ``uvicorn app.main:app --reload``
"""
import sys
from pathlib import Path

# 直接运行 ``python app/main.py`` 时，脚本所在目录(app/)会成为搜索路径，
# 导致 ``import app`` 失败。这里在导入 app 包之前把项目根目录加入 sys.path，
# 使终端直接运行与 PyCharm / ``python -m app.main`` 等方式都能正常工作。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI

from app.api.role import router as role_router
from app.api.user import router as user_router
from app.api.video import router as video_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger
from app.core.response import ApiResponse

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """应用工厂。"""
    app = FastAPI(
        title="用户管理服务",
        description="基于 FastAPI + SQLAlchemy 的用户增删改查服务",
        version="1.0.0",
        debug=settings.app_debug,
    )

    register_exception_handlers(app)
    app.include_router(user_router)
    app.include_router(role_router)
    app.include_router(video_router)

    @app.get("/health", tags=["系统"], summary="健康检查")
    def health() -> ApiResponse:
        """健康检查接口。"""
        return ApiResponse.ok({"status": "UP"})

    logger.info("应用初始化完成: %s", settings.app_name)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
