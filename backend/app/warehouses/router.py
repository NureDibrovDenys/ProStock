"""
REST API для складів.

Права доступу:
  GET  /api/v1/warehouses        — тільки адміністратор
  GET  /api/v1/warehouses/{id}   — будь-який авторизований користувач
  POST /api/v1/warehouses        — тільки адміністратор
  PATCH /api/v1/warehouses/{id}  — тільки адміністратор
  DELETE /api/v1/warehouses/{id} — тільки адміністратор
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.rbac import ADMIN_ROLES
from app.utils.role_checker import RoleChecker
from app.utils.security import get_current_user
from app.warehouses import crud
from app.warehouses.schemas import WarehouseCreate, WarehouseResponse, WarehouseUpdate

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouses"])

# Залежність: тільки root і administrator
require_admin = RoleChecker(*[role.value for role in ADMIN_ROLES])


def _to_response(warehouse) -> WarehouseResponse:
    """Перетворює ORM-об'єкт Warehouse у схему відповіді"""
    return WarehouseResponse(
        warehouse_id=warehouse.id,
        warehouse_name=warehouse.name,
        warehouse_address=warehouse.address,
        total_warehouse_area=warehouse.total_area,
    )


# ── READ ─────────────────────────────────────────────────────────────────────

@router.get(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Отримати склад за id",
    description="Повертає склад за його id. Доступно будь-якому авторизованому користувачу.",
)
async def get_warehouse(
    warehouse_id: int,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> WarehouseResponse:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    return _to_response(warehouse)


# ── READ (admin only) ────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[WarehouseResponse],
    summary="Список складів",
    description="Повертає всі склади. Доступно лише адміністраторам (root / administrator).",
)
async def list_warehouses(
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> list[WarehouseResponse]:
    warehouses = await crud.list_warehouses(session)
    return [_to_response(w) for w in warehouses]


# ── WRITE (admin only) ────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити склад",
    description="Створює новий склад. Доступно лише адміністраторам (root / administrator).",
)
async def create_warehouse(
    data: WarehouseCreate,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> WarehouseResponse:
    warehouse = await crud.create_warehouse(session, data)
    return _to_response(warehouse)


@router.patch(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Оновити склад",
    description=(
        "Частково оновлює склад (назва, адреса, площа). "
        "Передавайте лише ті поля, які потрібно змінити. "
        "Доступно лише адміністраторам (root / administrator)."
    ),
)
async def update_warehouse(
    warehouse_id: int,
    data: WarehouseUpdate,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> WarehouseResponse:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")

    if data.model_dump(exclude_none=True) == {}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Потрібно передати хоча б одне поле для оновлення",
        )

    warehouse = await crud.update_warehouse(session, warehouse, data)
    return _to_response(warehouse)


@router.delete(
    "/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити склад",
    description=(
        "Видаляє склад разом із усіма пов'язаними даними (каскадно). "
        "Доступно лише адміністраторам (root / administrator)."
    ),
)
async def delete_warehouse(
    warehouse_id: int,
    _: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    await crud.delete_warehouse(session, warehouse)
