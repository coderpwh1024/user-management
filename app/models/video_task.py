"""视频异步上传任务 ORM 模型，映射数据库表 ``t_video_task``。

新表遵循 CLAUDE.md 第四章规范：时间字段 ``gmt_create`` / ``gmt_modified``，
逻辑删除字段 ``is_deleted``。``task_id`` 为 UUID 全局唯一，
``status`` 三态用于异步任务在途统计与单设备并发限流。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VideoTask(Base):
    """视频异步上传任务表实体。"""

    __tablename__ = "t_video_task"

    # BigInteger 在 MySQL 映射为 BIGINT AUTO_INCREMENT；SQLite 仅 INTEGER 主键自增，
    # 故对 sqlite 退化为 Integer，保证内存 SQLite 集成测试可正常自增。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="任务ID（UUID，全局唯一）"
    )
    device_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="设备ID"
    )
    video_url: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="原始视频链接"
    )
    duration: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="视频时长(秒)"
    )
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="任务状态 0:处理中 1:成功 2:失败"
    )
    result_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="分析结果链接"
    )
    error_msg: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="失败原因"
    )
    is_deleted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="逻辑删除 0:未删除 1:已删除"
    )
    gmt_create: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    gmt_modified: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<VideoTask id={self.id} task_id={self.task_id!r} status={self.status}>"
