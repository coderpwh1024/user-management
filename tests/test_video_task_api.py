"""视频分析任务 API 集成测试。"""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud import video_task as video_task_crud
from app.db.session import Base, get_db
from app.main import app
from tests.test_video_task import FakeRedis


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """提供替换 MySQL 与 Redis 后的 API 客户端。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    redis_client = FakeRedis()

    def override_get_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    async def keep_processing(*_: object) -> None:
        return None

    async def create_fast(payload: object) -> tuple[str, str]:
        return video_task_crud.create_video_task_fast(payload, redis_client)  # type: ignore[arg-type]

    async def get_realtime(task_id: str) -> dict[str, str | None]:
        return video_task_crud.get_video_task_realtime(task_id, redis_client)

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(video_task_crud, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(video_task_crud, "create_video_task_fast_async", create_fast)
    monkeypatch.setattr(video_task_crud, "get_video_task_realtime_async", get_realtime)
    monkeypatch.setattr(video_task_crud, "analyze_video_task_async", keep_processing)
    monkeypatch.setattr(video_task_crud, "_enqueue_persistence", lambda _: None)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_upload_and_query_status(client: TestClient) -> None:
    """上传接口返回 taskId，状态接口实时返回 processing。"""
    response = client.post(
        "/api/video/upload",
        json={
            "deviceId": "device_api",
            "videoUrl": "https://example.com/video.mp4",
            "duration": 30,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    assert len(body["data"]["taskId"]) == 32

    status_response = client.get(
        f"/api/video/status/{body['data']['taskId']}"
    )
    status_body = status_response.json()
    assert status_body["code"] == 0
    assert status_body["data"]["taskId"] == body["data"]["taskId"]
    assert status_body["data"]["status"] == "processing"
    assert status_body["data"]["resultUrl"] is None
    assert status_body["data"]["createTime"]


def test_third_upload_returns_code_429(client: TestClient) -> None:
    """同设备第三次上传应返回 HTTP 200 与业务码 429。"""
    payload = {
        "deviceId": "device_limit",
        "videoUrl": "https://example.com/video.mp4",
        "duration": 30,
    }
    assert client.post("/api/video/upload", json=payload).json()["code"] == 0
    assert client.post("/api/video/upload", json=payload).json()["code"] == 0

    response = client.post("/api/video/upload", json=payload)
    assert response.status_code == 200
    assert response.json()["code"] == 429


def test_status_rejects_invalid_task_id(client: TestClient) -> None:
    """非法任务 ID 应由统一校验异常返回业务码 42200。"""
    response = client.get("/api/video/status/invalid")
    assert response.status_code == 200
    assert response.json()["code"] == 42200
