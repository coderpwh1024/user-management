"""视频分析任务 ORM 模型，映射数据库表 ``t_video_task``。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VideoTask(Base):
    """视频分析任务表实体。"""

    __tablename__ = "t_video_task"
    __table_args__ = (
        Index("uk_task_id", "task_id", unique=True),
        Index("idx_device_id_task_status", "device_id", "task_status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    task_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="任务ID（全局唯一）"
    )
    device_id: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="设备ID"
    )
    video_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, comment="待分析视频地址"
    )
    duration: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="视频时长（秒）"
    )
    task_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="任务状态 0:处理中(processing) 1:成功(success) 2:失败(failed)",
    )
    result_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, comment="分析结果地址，任务成功前为空"
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
        return f"<VideoTask id={self.id} task_id={self.task_id!r}>"
