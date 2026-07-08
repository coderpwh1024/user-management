"""Redis 客户端与配置单元测试。"""
from collections.abc import Iterator

import pytest
from redis.exceptions import RedisError

from app.core import redis as redis_core
from app.core.config import Settings


@pytest.fixture(autouse=True)
def reset_redis_client() -> Iterator[None]:
    """每个用例前后重置 Redis 客户端单例。"""
    redis_core._redis_client = None
    yield
    redis_core._redis_client = None


def test_redis_url_builds_with_encoded_password() -> None:
    """Redis 分项配置应构造带 URL 编码密码的连接串。"""
    settings = Settings(
        redis_dsn=None,
        redis_host="redis.local",
        redis_port=6380,
        redis_db=2,
        redis_password="p@ ss",
        _env_file=None,
    )
    assert settings.redis_url == "redis://:p%40%20ss@redis.local:6380/2"


def test_redis_url_prefers_dsn() -> None:
    """配置 REDIS_DSN 时应优先使用完整连接串。"""
    settings = Settings(
        redis_dsn="redis://:secret@cache.example.com:6379/3",
        redis_host="127.0.0.1",
        redis_port=6379,
        redis_db=0,
        _env_file=None,
    )
    assert settings.redis_url == "redis://:secret@cache.example.com:6379/3"


def test_get_redis_client_uses_settings_and_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """获取 Redis 客户端时应按配置创建连接池并复用单例。"""

    class FakeRedis:
        """用于替代 redis.Redis 的测试工厂。"""

        calls = 0
        last_url = ""
        last_kwargs: dict[str, object] = {}

        @classmethod
        def from_url(cls, url: str, **kwargs: object) -> "FakeRedis":
            """记录入参并返回客户端实例。"""
            cls.calls += 1
            cls.last_url = url
            cls.last_kwargs = kwargs
            return cls()

        def ping(self) -> bool:
            """模拟 Redis PING 成功。"""
            return True

        def close(self) -> None:
            """模拟关闭连接。"""
            return None

    monkeypatch.setattr(redis_core, "Redis", FakeRedis)
    monkeypatch.setattr(redis_core.settings, "redis_dsn", "redis://cache.local:6380/2")
    monkeypatch.setattr(redis_core.settings, "redis_max_connections", 11)
    monkeypatch.setattr(redis_core.settings, "redis_socket_timeout", 1.5)
    monkeypatch.setattr(redis_core.settings, "redis_socket_connect_timeout", 0.8)
    monkeypatch.setattr(redis_core.settings, "redis_health_check_interval", 20)

    first = redis_core.get_redis_client()
    second = redis_core.get_redis_client()

    assert first is second
    assert FakeRedis.calls == 1
    assert FakeRedis.last_url == "redis://cache.local:6380/2"
    assert FakeRedis.last_kwargs["decode_responses"] is True
    assert FakeRedis.last_kwargs["max_connections"] == 11
    assert FakeRedis.last_kwargs["socket_timeout"] == 1.5
    assert FakeRedis.last_kwargs["socket_connect_timeout"] == 0.8
    assert FakeRedis.last_kwargs["health_check_interval"] == 20


def test_ping_redis_returns_false_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis PING 异常时健康检查应返回 False。"""

    class BrokenRedis:
        """模拟不可用的 Redis 客户端。"""

        def ping(self) -> bool:
            """模拟连接异常。"""
            raise RedisError("connection refused")

    monkeypatch.setattr(redis_core, "get_redis_client", lambda: BrokenRedis())

    assert redis_core.ping_redis() is False


def test_close_redis_client_resets_singleton() -> None:
    """关闭 Redis 客户端后应清理单例。"""

    class FakeRedisClient:
        """模拟 Redis 客户端。"""

        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            """记录关闭动作。"""
            self.closed = True

    client = FakeRedisClient()
    redis_core._redis_client = client

    redis_core.close_redis_client()

    assert client.closed is True
    assert redis_core._redis_client is None
