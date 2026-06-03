"""角色 CRUD 集成测试（内存 SQLite）。

覆盖创建、唯一冲突、逻辑删除、更新等关键分支，验证查询自动过滤 is_deleted。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import BusinessException
from app.crud import role as role_crud
from app.crud.role import CODE_NOT_FOUND, CODE_ROLE_CODE_EXISTS
from app.db.session import Base
from app.models.role import Role  # noqa: F401  确保表被注册到 Base.metadata
from app.schemas.role import RoleCreate, RoleUpdate, StatusEnum


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


def _payload(role_code: str = "ADMIN", role_name: str = "管理员") -> RoleCreate:
    return RoleCreate(role_code=role_code, role_name=role_name, status=StatusEnum.ENABLED)


def test_create_and_get(db: Session) -> None:
    """创建后可按 ID 查回。"""
    role = role_crud.create_role(db, _payload())
    assert role.id is not None
    fetched = role_crud.get_role(db, role.id)
    assert fetched.role_code == "ADMIN"


def test_create_duplicate_code_raises(db: Session) -> None:
    """重复角色编码应抛唯一冲突。"""
    role_crud.create_role(db, _payload())
    with pytest.raises(BusinessException) as exc:
        role_crud.create_role(db, _payload())
    assert exc.value.code == CODE_ROLE_CODE_EXISTS


def test_logical_delete_then_not_found(db: Session) -> None:
    """逻辑删除后查询应视为不存在（is_deleted=1 被过滤）。"""
    role = role_crud.create_role(db, _payload())
    role_crud.delete_role(db, role.id)

    with pytest.raises(BusinessException) as exc:
        role_crud.get_role(db, role.id)
    assert exc.value.code == CODE_NOT_FOUND

    # 注意：role_code 上有 DB 唯一索引 uk_role_code，软删除行物理仍在，
    # 故被删除的编码不可直接重用（DB 唯一约束限制）。这是"唯一索引 + 逻辑删除"
    # 的固有约束，与 t_user.uk_id_card 一致。此处仅验证逻辑删除的过滤语义。


def test_update_partial(db: Session) -> None:
    """局部更新仅改传入字段。"""
    role = role_crud.create_role(db, _payload())
    updated = role_crud.update_role(
        db, role.id, RoleUpdate(role_name="超级管理员", status=StatusEnum.DISABLED)
    )
    assert updated.role_name == "超级管理员"
    assert updated.status == 0
    assert updated.role_code == "ADMIN"  # 未传入，保持不变


def test_list_filter_by_status(db: Session) -> None:
    """分页按状态过滤，且不返回已删除记录。"""
    role_crud.create_role(db, _payload("ADMIN", "管理员"))
    guest = role_crud.create_role(db, RoleCreate(role_code="GUEST", role_name="访客", status=StatusEnum.DISABLED))
    role_crud.delete_role(db, guest.id)

    items, total = role_crud.list_roles(db, status=1)
    assert total == 1
    assert items[0].role_code == "ADMIN"
