"""Redis 客户端模块。

统一创建 Redis 连接池客户端，供缓存、限流、分布式锁等基础能力复用。
"""
from redis import Redis, asyncio as redis_async
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_redis_client: Redis | None = None
_async_redis_client: redis_async.Redis | None = None


def get_redis_client() -> Redis:
    """获取 Redis 客户端单例。

    :return: Redis 客户端实例。
    """
    global _redis_client
    if _redis_client is None:
        logger.info(
            "初始化 Redis 客户端: host=%s, port=%s, db=%s",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
        )
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            health_check_interval=settings.redis_health_check_interval,
        )
    return _redis_client


def ping_redis() -> bool:
    """检查 Redis 是否可用。

    :return: Redis 可用返回 True，否则返回 False。
    """
    try:
        return bool(get_redis_client().ping())
    except RedisError as exc:
        logger.warning("Redis 健康检查失败: %s", exc)
        return False


def close_redis_client() -> None:
    """关闭 Redis 客户端连接池。"""
    global _redis_client
    if _redis_client is None:
        return

    try:
        _redis_client.close()
        logger.info("Redis 客户端已关闭")
    except RedisError as exc:
        logger.warning("关闭 Redis 客户端失败: %s", exc)
    finally:
        _redis_client = None


async def get_async_redis_client() -> redis_async.Redis:
    """获取异步 Redis 客户端单例，供异步 API 请求路径使用。"""
    global _async_redis_client
    if _async_redis_client is None:
        logger.info("初始化异步 Redis 客户端")
        _async_redis_client = redis_async.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            health_check_interval=settings.redis_health_check_interval,
        )
    return _async_redis_client


async def close_async_redis_client() -> None:
    """关闭异步 Redis 连接池。"""
    global _async_redis_client
    if _async_redis_client is not None:
        await _async_redis_client.aclose()
        _async_redis_client = None
