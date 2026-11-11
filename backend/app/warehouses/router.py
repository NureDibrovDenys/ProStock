"""
REST API для складів, стелажів і полиць.

Права доступу:
  GET  /api/v1/warehouses        — тільки адміністратор
  GET  /api/v1/warehouses/{id}   — будь-який авторизований користувач
  POST /api/v1/warehouses        — тільки адміністратор
  PATCH /api/v1/warehouses/{id}  — тільки адміністратор
  DELETE /api/v1/warehouses/{id} — тільки адміністратор

  GET  /api/v1/warehouses/{id}/racks               — будь-який авторизований
  GET  /api/v1/warehouses/{id}/racks/{rack_code}   — будь-який авторизований
  POST   /api/v1/warehouses/{id}/racks/{code}/shelves      — адмін / warehouse_manager
  PATCH  /api/v1/warehouses/{id}/racks/{code}/shelves/{id} — адмін / warehouse_manager
  DELETE /api/v1/warehouses/{id}/racks/{code}/shelves/{id} — адмін / warehouse_manager
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import RoleName
from app.core.rbac import ADMIN_ROLES, ALL_ROLES
from app.utils.role_checker import RoleChecker
from app.utils.security import get_current_user
from app.warehouses import crud
from app.warehouses.schemas import (
    RackDetailsResponse,
    RackSummaryResponse,
    ShelfCreate,
    ShelfInfoResponse,
    ShelfResponse,
    ShelfUpdate,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouses"])

# Залежність: тільки root і administrator
require_admin = RoleChecker(*[role.value for role in ADMIN_ROLES])

# Залежності для rack/shelf ендпоінтів
require_authenticated = RoleChecker(*[r.value for r in ALL_ROLES])
require_write = RoleChecker(*[r.value for r in ADMIN_ROLES | {RoleName.WAREHOUSE_MANAGER}])


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


# ── Rack helpers ──────────────────────────────────────────────────────────────

def _shelf_to_info(shelf) -> ShelfInfoResponse:
    return ShelfInfoResponse(
        shelf_id=shelf.id,
        shelf_code=shelf.code,
        product_name=None,
        occupied=1 if shelf.is_occupied else 0,
        capacity=1,
        shelf_status=shelf.status.value if hasattr(shelf.status, "value") else shelf.status,
    )


def _rack_to_summary(rack) -> RackSummaryResponse:
    total = max(len(rack.shelves), 1)
    occupied_count = sum(1 for s in rack.shelves if s.is_occupied)
    return RackSummaryResponse(
        rack_id=rack.id,
        rack_code=rack.code,
        shelves_count=len(rack.shelves) if rack.shelves else rack.shelves_count,
        fill_percent=round(occupied_count / total * 100, 1),
    )


def _shelf_to_response(shelf) -> ShelfResponse:
    return ShelfResponse(
        shelf_id=shelf.id,
        shelf_code=shelf.code,
        qr=shelf.qr,
        rack_id=shelf.rack_id,
        width=shelf.width,
        length=shelf.length,
        height=shelf.height,
        max_weight=shelf.max_weight,
        is_occupied=shelf.is_occupied,
        status=shelf.status.value if hasattr(shelf.status, "value") else shelf.status,
        inactive_reason=(
            shelf.inactive_reason.value
            if shelf.inactive_reason is not None and hasattr(shelf.inactive_reason, "value")
            else shelf.inactive_reason
        ),
        volume_m3=shelf.total_volume_m3,
    )


# ── Rack endpoints ────────────────────────────────────────────────────────────

@router.get(
    "/{warehouse_id}/racks",
    response_model=list[RackSummaryResponse],
    summary="Список стелажів складу",
)
async def list_racks(
    warehouse_id: int,
    _: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[RackSummaryResponse]:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    racks = await crud.get_racks_by_warehouse(session, warehouse_id)
    return [_rack_to_summary(r) for r in racks]


@router.get(
    "/{warehouse_id}/racks/{rack_code}",
    response_model=RackDetailsResponse,
    summary="Деталі стелажа з полицями",
)
async def get_rack(
    warehouse_id: int,
    rack_code: str,
    _: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> RackDetailsResponse:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стелаж не знайдено")
    return RackDetailsResponse(
        rack_id=rack.id,
        rack_code=rack.code,
        zone_name=None,
        updated_at=None,
        shelves=[_shelf_to_info(s) for s in rack.shelves],
    )


# ── Shelf endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/{warehouse_id}/racks/{rack_code}/shelves",
    response_model=ShelfResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити полицю у стелажі",
)
async def create_shelf(
    warehouse_id: int,
    rack_code: str,
    data: ShelfCreate,
    _: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> ShelfResponse:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стелаж не знайдено")
    try:
        shelf = await crud.create_shelf(session, rack, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _shelf_to_response(shelf)


@router.patch(
    "/{warehouse_id}/racks/{rack_code}/shelves/{shelf_id}",
    response_model=ShelfResponse,
    summary="Оновити полицю",
)
async def update_shelf(
    warehouse_id: int,
    rack_code: str,
    shelf_id: int,
    data: ShelfUpdate,
    _: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> ShelfResponse:
    if data.model_dump(exclude_none=True) == {}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Потрібно передати хоча б одне поле для оновлення",
        )
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стелаж не знайдено")
    shelf = await crud.get_shelf(session, shelf_id)
    if shelf is None or shelf.rack_id != rack.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Полицю не знайдено")
    shelf = await crud.update_shelf(session, shelf, data)
    return _shelf_to_response(shelf)


@router.delete(
    "/{warehouse_id}/racks/{rack_code}/shelves/{shelf_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити полицю",
)
async def delete_shelf(
    warehouse_id: int,
    rack_code: str,
    shelf_id: int,
    _: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стелаж не знайдено")
    shelf = await crud.get_shelf(session, shelf_id)
    if shelf is None or shelf.rack_id != rack.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Полицю не знайдено")
    await crud.delete_shelf(session, shelf)
