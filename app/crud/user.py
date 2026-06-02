"""用户持久层（CRUD）。

封装对 ``t_user`` 表的数据库操作，统一处理逻辑删除（is_delete）。
业务异常以 ``BusinessException`` 形式抛出。
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.logger import get_logger
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

logger = get_logger(__name__)

# 业务错误码
CODE_NOT_FOUND = 40400
CODE_ID_CARD_EXISTS = 40901


def _get_active(db: Session, user_id: int) -> Optional[User]:
    """按主键查询未删除用户。"""
    stmt = select(User).where(User.id == user_id, User.is_delete == 0)
    return db.execute(stmt).scalar_one_or_none()


def get_user(db: Session, user_id: int) -> User:
    """根据 ID 查询用户，不存在则抛出业务异常。"""
    user = _get_active(db, user_id)
    if user is None:
        logger.info("用户不存在: id=%s", user_id)
        raise BusinessException("用户不存在", CODE_NOT_FOUND)
    return user


def list_users(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    name: Optional[str] = None,
    phone: Optional[str] = None,
) -> tuple[list[User], int]:
    """分页查询用户列表，支持按姓名 / 手机号过滤。

    :return: (当前页数据, 总记录数)。
    """
    conditions = [User.is_delete == 0]
    if name:
        conditions.append(User.name.like(f"%{name}%"))
    if phone:
        conditions.append(User.phone == phone)

    total = db.execute(
        select(func.count()).select_from(User).where(*conditions)
    ).scalar_one()

    stmt = (
        select(User)
        .where(*conditions)
        .order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    logger.info("分页查询用户: page=%s, size=%s, total=%s", page, page_size, total)
    return items, total


def create_user(db: Session, data: UserCreate) -> User:
    """创建用户，身份证号需唯一。"""
    exists = db.execute(
        select(User).where(User.id_card == data.id_card, User.is_delete == 0)
    ).scalar_one_or_none()
    if exists is not None:
        logger.warning("身份证号已存在: id_card=%s", data.id_card)
        raise BusinessException("身份证号已存在", CODE_ID_CARD_EXISTS)

    user = User(
        name=data.name,
        age=data.age,
        phone=data.phone,
        id_card=data.id_card,
        gender=int(data.gender),
        create_by=data.create_by,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("创建用户成功: id=%s, name=%s", user.id, user.name)
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    """更新用户，仅更新传入的非空字段。"""
    user = get_user(db, user_id)

    update_fields = data.model_dump(exclude_unset=True, exclude_none=True)

    # 身份证号变更时校验唯一性
    new_id_card = update_fields.get("id_card")
    if new_id_card and new_id_card != user.id_card:
        exists = db.execute(
            select(User).where(
                User.id_card == new_id_card,
                User.is_delete == 0,
                User.id != user_id,
            )
        ).scalar_one_or_none()
        if exists is not None:
            logger.warning("身份证号已存在: id_card=%s", new_id_card)
            raise BusinessException("身份证号已存在", CODE_ID_CARD_EXISTS)

    if "gender" in update_fields:
        update_fields["gender"] = int(update_fields["gender"])

    for field, value in update_fields.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    logger.info("更新用户成功: id=%s, fields=%s", user_id, list(update_fields.keys()))
    return user


def delete_user(db: Session, user_id: int) -> None:
    """逻辑删除用户（is_delete=1）。"""
    user = get_user(db, user_id)
    user.is_delete = 1
    db.commit()
    logger.info("逻辑删除用户成功: id=%s", user_id)
