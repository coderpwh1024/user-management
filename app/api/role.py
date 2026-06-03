"""角色管理接口路由。

提供角色的增、删、改、查（含分页）RESTful 接口，
返回统一 ``ApiResponse`` 结构。
"""
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.response import ApiResponse
from app.crud import role as role_crud
from app.db.session import get_db
from app.schemas.role import RoleCreate, RoleOut, RolePage, RoleUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/roles", tags=["角色管理"])


@router.post("", summary="创建角色", response_model=ApiResponse[RoleOut])
def create_role(payload: RoleCreate, db: Session = Depends(get_db)) -> ApiResponse:
    """创建一个角色。"""
    logger.info("请求创建角色: role_code=%s", payload.role_code)
    role = role_crud.create_role(db, payload)
    return ApiResponse.ok(RoleOut.model_validate(role))


@router.get("/{role_id}", summary="查询角色详情", response_model=ApiResponse[RoleOut])
def get_role(
    role_id: int = Path(..., ge=1, description="角色ID"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """根据 ID 查询角色详情。"""
    logger.info("请求查询角色详情: id=%s", role_id)
    role = role_crud.get_role(db, role_id)
    return ApiResponse.ok(RoleOut.model_validate(role))


@router.get("", summary="分页查询角色", response_model=ApiResponse[RolePage])
def list_roles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    role_name: str | None = Query(None, description="角色名称（模糊匹配）"),
    status: int | None = Query(None, ge=0, le=1, description="状态 0:停用 1:启用"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """分页查询角色列表。"""
    logger.info("请求分页查询角色: page=%s, page_size=%s", page, page_size)
    items, total = role_crud.list_roles(db, page, page_size, role_name, status)
    data = RolePage(
        total=total,
        page=page,
        page_size=page_size,
        items=[RoleOut.model_validate(r) for r in items],
    )
    return ApiResponse.ok(data)


@router.put("/{role_id}", summary="更新角色", response_model=ApiResponse[RoleOut])
def update_role(
    payload: RoleUpdate,
    role_id: int = Path(..., ge=1, description="角色ID"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """更新角色信息（仅更新传入字段）。"""
    logger.info("请求更新角色: id=%s", role_id)
    role = role_crud.update_role(db, role_id, payload)
    return ApiResponse.ok(RoleOut.model_validate(role))


@router.delete("/{role_id}", summary="删除角色", response_model=ApiResponse[None])
def delete_role(
    role_id: int = Path(..., ge=1, description="角色ID"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """逻辑删除角色。"""
    logger.info("请求删除角色: id=%s", role_id)
    role_crud.delete_role(db, role_id)
    return ApiResponse.ok(message="删除成功")
