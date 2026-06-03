"""角色持久层（CRUD）。

封装对 ``t_role`` 表的数据库操作，统一处理逻辑删除（is_deleted）。
业务异常以 ``BusinessException`` 形式抛出。
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.logger import get_logger
from app.models.role import Role
from app.schemas.role import RoleCreate, RoleUpdate

logger = get_logger(__name__)

# 业务错误码
CODE_NOT_FOUND = 40400
CODE_ROLE_CODE_EXISTS = 40901


def _get_active(db: Session, role_id: int) -> Optional[Role]:
    """按主键查询未删除角色。"""
    stmt = select(Role).where(Role.id == role_id, Role.is_deleted == 0)
    return db.execute(stmt).scalar_one_or_none()


def get_role(db: Session, role_id: int) -> Role:
    """根据 ID 查询角色，不存在则抛出业务异常。"""
    role = _get_active(db, role_id)
    if role is None:
        logger.info("角色不存在: id=%s", role_id)
        raise BusinessException("角色不存在", CODE_NOT_FOUND)
    return role


def list_roles(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    role_name: Optional[str] = None,
    status: Optional[int] = None,
) -> tuple[list[Role], int]:
    """分页查询角色列表，支持按角色名称模糊、状态过滤。

    :return: (当前页数据, 总记录数)。
    """
    conditions = [Role.is_deleted == 0]
    if role_name:
        conditions.append(Role.role_name.like(f"%{role_name}%"))
    if status is not None:
        conditions.append(Role.status == status)

    total = db.execute(
        select(func.count()).select_from(Role).where(*conditions)
    ).scalar_one()

    stmt = (
        select(Role)
        .where(*conditions)
        .order_by(Role.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    logger.info("分页查询角色: page=%s, size=%s, total=%s", page, page_size, total)
    return items, total


def create_role(db: Session, data: RoleCreate) -> Role:
    """创建角色，角色编码需全局唯一。"""
    exists = db.execute(
        select(Role).where(Role.role_code == data.role_code, Role.is_deleted == 0)
    ).scalar_one_or_none()
    if exists is not None:
        logger.warning("角色编码已存在: role_code=%s", data.role_code)
        raise BusinessException("角色编码已存在", CODE_ROLE_CODE_EXISTS)

    role = Role(
        role_code=data.role_code,
        role_name=data.role_name,
        status=int(data.status),
        create_by=data.create_by,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    logger.info("创建角色成功: id=%s, role_code=%s", role.id, role.role_code)
    return role


def update_role(db: Session, role_id: int, data: RoleUpdate) -> Role:
    """更新角色，仅更新传入的非空字段。"""
    role = get_role(db, role_id)

    update_fields = data.model_dump(exclude_unset=True, exclude_none=True)

    # 角色编码变更时校验唯一性
    new_code = update_fields.get("role_code")
    if new_code and new_code != role.role_code:
        exists = db.execute(
            select(Role).where(
                Role.role_code == new_code,
                Role.is_deleted == 0,
                Role.id != role_id,
            )
        ).scalar_one_or_none()
        if exists is not None:
            logger.warning("角色编码已存在: role_code=%s", new_code)
            raise BusinessException("角色编码已存在", CODE_ROLE_CODE_EXISTS)

    if "status" in update_fields:
        update_fields["status"] = int(update_fields["status"])

    for field, value in update_fields.items():
        setattr(role, field, value)

    db.commit()
    db.refresh(role)
    logger.info("更新角色成功: id=%s, fields=%s", role_id, list(update_fields.keys()))
    return role


def delete_role(db: Session, role_id: int) -> None:
    """逻辑删除角色（is_deleted=1）。"""
    role = get_role(db, role_id)
    role.is_deleted = 1
    db.commit()
    logger.info("逻辑删除角色成功: id=%s", role_id)
