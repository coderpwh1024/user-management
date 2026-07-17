"""视频分析任务 ORM 模型，映射 ``t_video_task`` 表。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

_TINYINT_UNSIGNED = TINYINT(unsigned=True).with_variant(Integer, "sqlite")


class VideoTask(Base):
    """视频分析任务实体。"""

    __tablename__ = "t_video_task"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True,
        autoincrement=True, comment="主键ID"
    )
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="任务唯一标识")
    device_id: Mapped[str] = mapped_column(String(32), nullable=False, comment="设备唯一标识")
    video_url: Mapped[str] = mapped_column(String(2048), nullable=False, comment="视频地址")
    duration: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, comment="视频时长，单位秒")
    task_status: Mapped[int] = mapped_column(
        _TINYINT_UNSIGNED, nullable=False, default=0,
        comment="任务状态 0:等待处理 1:处理中 2:处理成功 3:处理失败"
    )
    result_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, comment="分析结果地址")
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="失败原因")
    is_deleted: Mapped[int] = mapped_column(
        _TINYINT_UNSIGNED, nullable=False, default=0, comment="逻辑删除 0:未删除 1:已删除"
    )
    gmt_create: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")
    gmt_modified: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:
        """返回便于日志定位的实体描述。"""
        return f"<VideoTask id={self.id} task_id={self.task_id!r}>"
