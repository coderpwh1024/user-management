"""数据库会话与引擎管理。

基于 SQLAlchemy 2.0 构建引擎、会话工厂，并提供 FastAPI 依赖注入
使用的 ``get_db`` 生成器。
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# 数据库引擎
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    echo=settings.app_debug,
)

# 会话工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """ORM 模型基类。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供数据库会话并保证关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
