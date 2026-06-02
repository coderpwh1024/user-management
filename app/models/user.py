"""用户 ORM 模型，映射数据库表 ``t_user``。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    """用户表实体。"""

    __tablename__ = "t_user"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="姓名")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="年龄")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, comment="手机号")
    id_card: Mapped[str] = mapped_column(
        String(18), nullable=False, unique=True, comment="身份证号"
    )
    gender: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="性别 0:未知 1:男 2:女"
    )
    is_delete: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="逻辑删除 0:未删除 1:已删除"
    )
    create_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="创建人"
    )
    update_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="更新人"
    )
    create_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r}>"
