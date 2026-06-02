"""业务异常定义与全局异常处理。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import get_logger
from app.core.response import ApiResponse

logger = get_logger(__name__)


class BusinessException(Exception):
    """业务异常基类。

    用于在 service / crud 层抛出可预期的业务错误，
    由全局异常处理器统一转换为标准响应。
    """

    def __init__(self, message: str, code: int = 40000):
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(BusinessException)
    async def _business_handler(_: Request, exc: BusinessException) -> JSONResponse:
        logger.warning("业务异常: code=%s, message=%s", exc.code, exc.message)
        return JSONResponse(
            status_code=200,
            content=ApiResponse.fail(exc.code, exc.message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        msg = f"参数校验失败: {field} {first.get('msg', '')}".strip()
        logger.warning("参数校验失败: %s", errors)
        return JSONResponse(
            status_code=200,
            content=ApiResponse.fail(42200, msg).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.fail(exc.status_code, str(exc.detail)).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _global_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("系统未知异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ApiResponse.fail(50000, "系统内部错误").model_dump(),
        )
