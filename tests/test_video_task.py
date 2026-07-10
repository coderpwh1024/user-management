"""视频分析任务 CRUD、Redis 限流与异步状态测试。"""
import asyncio
from collections.abc import Iterator

import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import BusinessException
from app.crud import video_task as video_task_crud
from app.db.session import Base
from app.schemas.video_task import VideoTaskCreate, VideoTaskStatus, VideoTaskStatusCode


class FakeRedis:
    """仅实现任务槽位 Lua 语义的 Redis 测试替身。"""

    def __init__(self) -> None:
        self.active_tasks: dict[str, set[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    def pipeline(self, transaction: bool = True) -> "FakeRedis":
        """模拟 Redis pipeline。"""
        return self

    def hset(self, key: str, mapping: dict[str, object]) -> int:
        """模拟哈希写入。"""
        self.hashes.setdefault(key, {}).update(
            {field: str(value) for field, value in mapping.items()}
        )
        return len(mapping)

    def hgetall(self, key: str) -> dict[str, str]:
        """模拟哈希读取。"""
        return dict(self.hashes.get(key, {}))

    def expire(self, key: str, _: int) -> bool:
        """模拟过期设置。"""
        return key in self.hashes

    def execute(self) -> list[object]:
        """模拟事务提交。"""
        return []

    def delete(self, key: str) -> int:
        """模拟删除。"""
        self.hashes.pop(key, None)
        return 1

    def eval(self, script: str, _: int, key: str, *args: object) -> int:
        """模拟 Redis Lua 原子执行。"""
        task_id = str(args[0])
        tasks = self.active_tasks.setdefault(key, set())
        if "SADD" in script:
            task_limit = int(args[1])
            if len(tasks) >= task_limit:
                return 0
            tasks.add(task_id)
            return 1
        tasks.discard(task_id)
        if not tasks:
            self.active_tasks.pop(key, None)
        return 1


class BrokenRedis:
    """始终不可用的 Redis 测试替身。"""

    def eval(self, *_: object) -> int:
        """模拟 Redis 连接异常。"""
        raise RedisError("redis unavailable")


class AsyncFakeRedis:
    """异步 Redis 测试替身。"""

    def __init__(self, sync_client: FakeRedis) -> None:
        self.sync_client = sync_client

    async def eval(self, script: str, count: int, key: str, *args: object) -> int:
        """模拟异步 Lua 执行。"""
        return self.sync_client.eval(script, count, key, *args)

    async def hgetall(self, key: str) -> dict[str, str]:
        """模拟异步哈希读取。"""
        return self.sync_client.hgetall(key)

    async def hset(self, key: str, mapping: dict[str, str]) -> int:
        """模拟异步哈希写入。"""
        return self.sync_client.hset(key, mapping)

    async def expire(self, key: str, seconds: int) -> bool:
        """模拟异步过期设置。"""
        return self.sync_client.expire(key, seconds)

    async def delete(self, key: str) -> int:
        """模拟异步删除。"""
        return self.sync_client.delete(key)

    def pipeline(self, transaction: bool = True) -> "AsyncFakeRedis":
        """模拟异步 pipeline。"""
        return self

    async def execute(self) -> list[object]:
        """模拟异步事务提交。"""
        return []


@pytest.fixture()
def session_factory() -> Iterator[sessionmaker[Session]]:
    """提供跨会话共享的内存 SQLite 会话工厂。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """提供测试数据库会话。"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _payload(device_id: str = "device_001") -> VideoTaskCreate:
    """构造合法的视频上传请求。"""
    return VideoTaskCreate(
        deviceId=device_id,
        videoUrl="https://example.com/video.mp4",
        duration=30,
    )


def test_create_and_get_processing_task(db: Session) -> None:
    """新任务应持久化为处理中状态，且任务 ID 为 32 位。"""
    task = video_task_crud.create_video_task(db, _payload(), FakeRedis())

    assert len(task.task_id) == 32
    assert task.task_status == VideoTaskStatusCode.PROCESSING
    assert video_task_crud.get_video_task(db, task.task_id).id == task.id
    assert video_task_crud.to_api_status(task.task_status) == VideoTaskStatus.PROCESSING


def test_async_fast_path_uses_redis_before_mysql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """异步快速路径应可在不打开 MySQL 会话的情况下返回实时任务。"""
    redis_client = AsyncFakeRedis(FakeRedis())

    async def get_client() -> AsyncFakeRedis:
        return redis_client

    monkeypatch.setattr(video_task_crud, "get_async_redis_client", get_client)
    monkeypatch.setattr(video_task_crud, "_enqueue_persistence", lambda _: None)
    task_id, device_id = asyncio.run(
        video_task_crud.create_video_task_fast_async(_payload())
    )
    view = asyncio.run(video_task_crud.get_video_task_realtime_async(task_id))

    assert device_id == "device_001"
    assert view["task_id"] == task_id
    assert view["status"] == "processing"


def test_single_device_allows_only_two_active_tasks(db: Session) -> None:
    """同一设备第三个并发任务应返回自定义业务码 429。"""
    redis_client = FakeRedis()
    video_task_crud.create_video_task(db, _payload(), redis_client)
    video_task_crud.create_video_task(db, _payload(), redis_client)

    with pytest.raises(BusinessException) as exc:
        video_task_crud.create_video_task(db, _payload(), redis_client)

    assert exc.value.code == video_task_crud.CODE_DEVICE_TASK_LIMIT
    assert exc.value.code == 429


def test_different_devices_have_independent_limits(db: Session) -> None:
    """不同设备的并发槽位互不影响。"""
    redis_client = FakeRedis()
    first = video_task_crud.create_video_task(db, _payload("device_a"), redis_client)
    second = video_task_crud.create_video_task(db, _payload("device_b"), redis_client)
    assert first.device_id != second.device_id


def test_redis_unavailable_rejects_task(db: Session) -> None:
    """Redis 不可用时应拒绝任务，避免并发限制失效。"""
    with pytest.raises(BusinessException) as exc:
        video_task_crud.create_video_task(db, _payload(), BrokenRedis())
    assert exc.value.code == video_task_crud.CODE_REDIS_UNAVAILABLE


def test_async_analysis_marks_success_and_releases_slot(
    db: Session,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """异步分析完成后应写入成功状态、结果地址并释放槽位。"""
    redis_client = FakeRedis()
    task = video_task_crud.create_video_task(db, _payload(), redis_client)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(video_task_crud.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(video_task_crud, "SessionLocal", session_factory)
    asyncio.run(
        video_task_crud.analyze_video_task(
            task.task_id,
            task.device_id,
            redis_client,
        )
    )

    db.expire_all()
    finished = video_task_crud.get_video_task(db, task.task_id)
    assert finished.task_status == VideoTaskStatusCode.SUCCESS
    assert finished.result_url is not None
    assert redis_client.active_tasks == {}


def test_analysis_exception_marks_failed(
    db: Session,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """分析异常时应标记 failed，并保证释放设备槽位。"""
    redis_client = FakeRedis()
    task = video_task_crud.create_video_task(db, _payload(), redis_client)

    async def no_sleep(_: float) -> None:
        return None

    def fail_result_url(_: str) -> str:
        raise RuntimeError("analysis failed")

    monkeypatch.setattr(video_task_crud.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(video_task_crud, "SessionLocal", session_factory)
    monkeypatch.setattr(video_task_crud, "_build_result_url", fail_result_url)
    asyncio.run(
        video_task_crud.analyze_video_task(
            task.task_id,
            task.device_id,
            redis_client,
        )
    )

    db.expire_all()
    failed = video_task_crud.get_video_task(db, task.task_id)
    assert failed.task_status == VideoTaskStatusCode.FAILED
    assert failed.result_url is None
    assert redis_client.active_tasks == {}


def test_logical_delete_filters_task(db: Session) -> None:
    """逻辑删除后任务查询应返回不存在。"""
    task = video_task_crud.create_video_task(db, _payload(), FakeRedis())
    video_task_crud.delete_video_task(db, task.task_id)

    with pytest.raises(BusinessException) as exc:
        video_task_crud.get_video_task(db, task.task_id)
    assert exc.value.code == video_task_crud.CODE_NOT_FOUND


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"deviceId": "", "videoUrl": "https://example.com/a.mp4", "duration": 1}, "deviceId"),
        ({"deviceId": "dev", "videoUrl": "not-a-url", "duration": 1}, "videoUrl"),
        ({"deviceId": "dev", "videoUrl": "https://example.com/a.mp4", "duration": 0}, "duration"),
    ],
)
def test_upload_schema_rejects_invalid_fields(
    payload: dict[str, object], field: str
) -> None:
    """上传字段非法时 Pydantic 应拒绝请求。"""
    with pytest.raises(ValueError) as exc:
        VideoTaskCreate.model_validate(payload)
    assert field in str(exc.value)
