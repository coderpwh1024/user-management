"""日志模块。

统一配置应用日志格式与级别，供各层通过 ``get_logger`` 获取 logger。
"""
import logging
import sys

from app.core.config import settings

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)

_configured = False


def _setup() -> None:
    """初始化根 logger（仅执行一次）。"""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger。

    :param name: logger 名称，建议传入 ``__name__``。
    :return: 已配置的 logger 实例。
    """
    _setup()
    return logging.getLogger(name)
