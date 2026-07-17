"""视频分析任务的 CRUD 与异步状态测试。"""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import BusinessException
from app.crud import video_task as video_task_crud
from app.crud.video_task import CODE_DEVICE_TASK_LIMIT, CODE_NOT_FOUND
from app.db.session import Base
from app.models.video_task import VideoTask  # noqa: F401 确保注册模型
from app.schemas.video_task import VideoUploadCreate


class FakeRedis:
    """可验证 Lua 限流行为的简易 Redis 替身。"""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def eval(self, script: str, _: int, key: str, *args: object) -> int:
        """模拟申请和释放设备槽位脚本。"""
        if "INCR" in script:
            limit = int(args[0])
            current = self.values.get(key, 0)
            if current >= limit:
                return 0
            self.values[key] = current + 1
            return self.values[key]
        current = self.values.get(key, 0)
        if current <= 1:
            self.values.pop(key, None)
            return 0
        self.values[key] = current - 1
        return self.values[key]


@pytest.fixture()
def db() -> Session:
    """提供独立 SQLite 数据库会话。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _payload(device_id: str = "device-001") -> VideoUploadCreate:
    """构造合法视频上报请求。"""
    return VideoUploadCreate(
        deviceId=device_id,
        videoUrl="https://example.com/input.mp4",
        duration=Decimal("3.000"),
    )


def test_create_task_and_query_status(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    """任务创建后应为 pending，状态查询使用对外字符串。"""
    monkeypatch.setattr(video_task_crud, "get_redis_client", lambda: FakeRedis())
    task = video_task_crud.create_video_task(db, _payload())

    data = video_task_crud.get_video_status(db, task.task_id)
    assert len(task.task_id) == 32
    assert data["status"] == "pending"
    assert data["result_url"] is None


def test_same_device_rejects_third_outstanding_task(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    """同一设备第三个未完成任务必须返回业务码 429。"""
    fake_redis = FakeRedis()
    monkeypatch.setattr(video_task_crud, "get_redis_client", lambda: fake_redis)
    video_task_crud.create_video_task(db, _payload())
    video_task_crud.create_video_task(db, _payload())

    with pytest.raises(BusinessException) as exc:
        video_task_crud.create_video_task(db, _payload())
    assert exc.value.code == CODE_DEVICE_TASK_LIMIT


def test_process_task_marks_success_and_releases_slot(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    """异步处理完成后任务应成功，并释放 Redis 槽位。"""
    fake_redis = FakeRedis()
    monkeypatch.setattr(video_task_crud, "get_redis_client", lambda: fake_redis)
    task = video_task_crud.create_video_task(db, _payload())
    monkeypatch.setattr(video_task_crud, "SessionLocal", lambda: db)
    monkeypatch.setattr(video_task_crud.time, "sleep", lambda _: None)

    video_task_crud.process_video_task(task.task_id)
    assert video_task_crud.get_video_status(db, task.task_id)["status"] == "success"
    assert not fake_redis.values


def test_get_missing_task_raises_not_found(db: Session) -> None:
    """不存在的任务应抛出 40400。"""
    with pytest.raises(BusinessException) as exc:
        video_task_crud.get_video_task(db, "0" * 32)
    assert exc.value.code == CODE_NOT_FOUND
