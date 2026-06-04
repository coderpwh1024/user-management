"""视频任务 CRUD 与 service 集成测试（内存 SQLite）。

覆盖：创建、按 task_id 查询、不存在分支、状态流转（成功 / 失败）、
在途计数，以及 service 层「单设备最多 2 个在途任务」的并发限流（429）。
"""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import BusinessException
from app.crud import video_task as video_crud
from app.crud.video_task import CODE_DEVICE_LIMIT, CODE_NOT_FOUND
from app.db.session import Base
from app.models.video_task import VideoTask  # noqa: F401  注册表到 Base.metadata
from app.schemas.video_task import VideoStatusEnum


@pytest.fixture()
def db() -> Session:
    """提供一个独立的内存 SQLite 会话。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


# --------------------------- crud 层测试 ---------------------------

def test_create_and_get(db: Session) -> None:
    """创建后可按 task_id 查回，初始为处理中。"""
    task = video_crud.create_task(db, "tid-1", "dev-1", "https://x.com/v.mp4", 30)
    assert task.id is not None
    assert task.status == int(VideoStatusEnum.PROCESSING)

    fetched = video_crud.get_by_task_id(db, "tid-1")
    assert fetched.device_id == "dev-1"
    assert fetched.duration == 30


def test_get_not_found_raises(db: Session) -> None:
    """查询不存在的 task_id 抛 40400。"""
    with pytest.raises(BusinessException) as exc:
        video_crud.get_by_task_id(db, "no-such-task")
    assert exc.value.code == CODE_NOT_FOUND


def test_mark_success(db: Session) -> None:
    """标记成功后状态为 1 且写入结果链接。"""
    video_crud.create_task(db, "tid-2", "dev-1", "https://x.com/v.mp4", None)
    video_crud.mark_success(db, "tid-2", "https://result.example.com/tid-2.json")

    task = video_crud.get_by_task_id(db, "tid-2")
    assert task.status == int(VideoStatusEnum.SUCCESS)
    assert task.result_url.endswith("tid-2.json")


def test_mark_failed(db: Session) -> None:
    """标记失败后状态为 2 且记录失败原因。"""
    video_crud.create_task(db, "tid-3", "dev-1", "https://x.com/v.mp4", None)
    video_crud.mark_failed(db, "tid-3", "上传超时")

    task = video_crud.get_by_task_id(db, "tid-3")
    assert task.status == int(VideoStatusEnum.FAILED)
    assert task.error_msg == "上传超时"


def test_count_active_by_device(db: Session) -> None:
    """在途计数仅统计处理中且未删除的任务。"""
    video_crud.create_task(db, "a1", "dev-X", "https://x.com/v.mp4", None)
    video_crud.create_task(db, "a2", "dev-X", "https://x.com/v.mp4", None)
    video_crud.create_task(db, "b1", "dev-Y", "https://x.com/v.mp4", None)
    video_crud.mark_success(db, "a2", "https://r.com/a2.json")  # 处理完不再计入

    assert video_crud.count_active_by_device(db, "dev-X") == 1
    assert video_crud.count_active_by_device(db, "dev-Y") == 1


# --------------------------- service 限流测试 ---------------------------

@pytest.fixture()
def shared_engine():
    """提供跨线程共享的内存 SQLite 引擎（service 用 to_thread 操作 DB）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


def test_submit_upload_device_limit(monkeypatch, shared_engine) -> None:
    """单设备第 3 个在途任务应被限流（code=429）。"""
    from app.services import video_task as video_service

    test_session = sessionmaker(
        bind=shared_engine, autoflush=False, expire_on_commit=False
    )
    # 将 service 使用的会话工厂指向内存库，并屏蔽真实 3 秒后台任务
    monkeypatch.setattr(video_service, "SessionLocal", test_session)
    monkeypatch.setattr(video_service, "schedule_processing", lambda task_id: None)
    # 清空模块级设备锁，避免历史 Lock 绑定到已关闭的事件循环
    video_service._device_locks.clear()

    async def _run() -> None:
        tid1 = await video_service.submit_upload("dev-1", "https://x.com/1.mp4", 10)
        tid2 = await video_service.submit_upload("dev-1", "https://x.com/2.mp4", 10)
        assert tid1 and tid2 and tid1 != tid2

        # 第 3 个在途任务超限
        with pytest.raises(BusinessException) as exc:
            await video_service.submit_upload("dev-1", "https://x.com/3.mp4", 10)
        assert exc.value.code == CODE_DEVICE_LIMIT

        # 不同设备不受影响
        tid_other = await video_service.submit_upload("dev-2", "https://x.com/4.mp4", 10)
        assert tid_other

    asyncio.run(_run())
