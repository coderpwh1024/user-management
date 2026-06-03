"""角色 ORM 模型，映射数据库表 ``t_role``。

新表遵循 CLAUDE.md 第四章规范：时间字段 ``gmt_create`` / ``gmt_modified``，
逻辑删除字段 ``is_deleted``（区别于历史遗留表 ``t_user`` 的旧命名）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Role(Base):
    """角色表实体。"""

    __tablename__ = "t_role"

    # BigInteger 在 MySQL 映射为 BIGINT AUTO_INCREMENT；SQLite 仅 INTEGER 主键自增，
    # 故对 sqlite 退化为 Integer，保证内存 SQLite 集成测试可正常自增。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    role_code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="角色编码（全局唯一）"
    )
    role_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="角色名称"
    )
    status: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="状态 0:停用 1:启用"
    )
    is_deleted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="逻辑删除 0:未删除 1:已删除"
    )
    create_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="创建人"
    )
    update_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="更新人"
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
        return f"<Role id={self.id} role_code={self.role_code!r}>"
