"""用户管理接口路由。

提供用户的增、删、改、查（含分页）RESTful 接口，
返回统一 ``ApiResponse`` 结构。
"""
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.response import ApiResponse
from app.crud import user as user_crud
from app.db.session import get_db
from app.schemas.user import UserCreate, UserOut, UserPage, UserUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["用户管理"])


@router.post("", summary="创建用户", response_model=ApiResponse[UserOut])
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> ApiResponse:
    """创建一个用户。"""
    logger.info("请求创建用户: name=%s, phone=%s", payload.name, payload.phone)
    user = user_crud.create_user(db, payload)
    return ApiResponse.ok(UserOut.model_validate(user))


@router.get("/{user_id}", summary="查询用户详情", response_model=ApiResponse[UserOut])
def get_user(
    user_id: int = Path(..., ge=1, description="用户ID"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """根据 ID 查询用户详情。"""
    logger.info("请求查询用户详情: id=%s", user_id)
    user = user_crud.get_user(db, user_id)
    return ApiResponse.ok(UserOut.model_validate(user))


@router.get("", summary="分页查询用户", response_model=ApiResponse[UserPage])
def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    name: str | None = Query(None, description="姓名（模糊匹配）"),
    phone: str | None = Query(None, description="手机号（精确匹配）"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """分页查询用户列表。"""
    logger.info("请求分页查询用户: page=%s, page_size=%s", page, page_size)
    items, total = user_crud.list_users(db, page, page_size, name, phone)
    data = UserPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserOut.model_validate(u) for u in items],
    )
    return ApiResponse.ok(data)


@router.put("/{user_id}", summary="更新用户", response_model=ApiResponse[UserOut])
def update_user(
    payload: UserUpdate,
    user_id: int = Path(..., ge=1, description="用户ID"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """更新用户信息（仅更新传入字段）。"""
    logger.info("请求更新用户: id=%s", user_id)
    user = user_crud.update_user(db, user_id, payload)
    return ApiResponse.ok(UserOut.model_validate(user))


@router.delete("/{user_id}", summary="删除用户", response_model=ApiResponse[None])
def delete_user(
    user_id: int = Path(..., ge=1, description="用户ID"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """逻辑删除用户。"""
    logger.info("请求删除用户: id=%s", user_id)
    user_crud.delete_user(db, user_id)
    return ApiResponse.ok(message="删除成功")
