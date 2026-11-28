
from __future__ import annotations
from os import stat

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import RoleName
from app.core.rbac import ADMIN_ROLES, ALL_ROLES
from app.utils.role_checker import RoleChecker
from app.routers.map import _check_warehouse_access
from app.utils.security import get_current_user
from app.warehouses import crud
from app.warehouses.services import fill_service
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
    LpnContainerResponse
    
)
from app.stock.service import create_lpn_container

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouses"])

require_admin = RoleChecker(*[role.value for role in ADMIN_ROLES])

require_authenticated = RoleChecker(*[r.value for r in ALL_ROLES])
require_write = RoleChecker(*[r.value for r in ADMIN_ROLES | {RoleName.WAREHOUSE_MANAGER}])

def _to_response(warehouse) -> WarehouseResponse:
    
    return WarehouseResponse(
        warehouse_id=warehouse.id,
        warehouse_name=warehouse.name,
        warehouse_address=warehouse.address,
        total_warehouse_area=warehouse.total_area,
    )

def check_shelf_warehouse_access(
    current_user: dict,
    warehouse_id: int,
) -> None:
    

    admin_roles = {role.value for role in ADMIN_ROLES}

    if current_user["role"] in admin_roles:
        return

    if current_user.get("warehouse_id") != warehouse_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас немає доступу до цього складу",
        )

@router.get(
    "/{warehouse_id}",
    response_model=WarehouseResponse,
    summary="Отримати склад за id",
    description="Повертає склад за його id. Доступно будь-якому авторизованому користувачу.",
)
async def get_warehouse(
    warehouse_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> WarehouseResponse:
    _check_warehouse_access(current_user, warehouse_id)
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    return _to_response(warehouse)

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

    if data.model_dump(exclude_unset=True) == {}:
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

def _is_occupied(shelf, fill=None) -> bool:
    # Проведення накладних кладе товар у stock_item, але прапорець shelf.is_occupied не чіпає
    return bool(shelf.is_occupied or (fill is not None and fill.items_count > 0))

def _shelf_to_info(shelf, fill=None) -> ShelfInfoResponse:
    used_volume = float(fill.used_volume_m3) if fill is not None else 0.0
    used_weight = float(fill.used_weight_kg) if fill is not None else 0.0
    total_volume = float(fill.total_volume_m3) if fill is not None else shelf.total_volume_m3
    total_weight = (
        float(fill.total_max_weight_kg) if fill is not None else float(shelf.max_weight)
    )
    return ShelfInfoResponse(
        shelf_id=shelf.id,
        shelf_code=shelf.code,
        product_name=None,
        occupied=1 if _is_occupied(shelf, fill) else 0,
        capacity=1,
        shelf_status=shelf.status.value if hasattr(shelf.status, "value") else shelf.status,
        volume_fill_percent=fill.volume_fill_percent if fill is not None else 0.0,
        weight_fill_percent=fill.weight_fill_percent if fill is not None else 0.0,
        used_volume_m3=round(used_volume, 4),
        total_volume_m3=round(total_volume, 4),
        used_weight_kg=round(used_weight, 3),
        total_max_weight_kg=round(total_weight, 3),
        items_count=fill.items_count if fill is not None else 0,
        overloaded=fill.is_overloaded if fill is not None else False,
    )

def _rack_to_summary(rack, fill=None) -> RackSummaryResponse:
    shelves_count = len(rack.shelves) if rack.shelves else rack.shelves_count
    if fill is None:
        return RackSummaryResponse(
            rack_id=rack.id,
            rack_code=rack.code,
            shelves_count=shelves_count,
            fill_percent=0.0,
        )
    return RackSummaryResponse(
        rack_id=rack.id,
        rack_code=rack.code,
        shelves_count=shelves_count,
        fill_percent=fill.volume_fill_percent,
        volume_fill_percent=fill.volume_fill_percent,
        weight_fill_percent=fill.weight_fill_percent,
        used_volume_m3=round(float(fill.used_volume_m3), 4),
        total_volume_m3=round(float(fill.total_volume_m3), 4),
        used_weight_kg=round(float(fill.used_weight_kg), 3),
        total_max_weight_kg=round(float(fill.total_max_weight_kg), 3),
        shelves_used=fill.shelves_used,
        overloaded=fill.is_overloaded,
    )

def _shelf_to_response(shelf, fill=None) -> ShelfResponse:
    used_volume = float(fill.used_volume_m3) if fill is not None else 0.0
    used_weight = float(fill.used_weight_kg) if fill is not None else 0.0
    total_volume = float(fill.total_volume_m3) if fill is not None else shelf.total_volume_m3
    total_weight = (
        float(fill.total_max_weight_kg) if fill is not None else float(shelf.max_weight)
    )
    return ShelfResponse(
        shelf_id=shelf.id,
        shelf_code=shelf.code,
        qr=shelf.qr,
        rack_id=shelf.rack_id,
        width=shelf.width,
        length=shelf.length,
        height=shelf.height,
        max_weight=shelf.max_weight,
        is_occupied=_is_occupied(shelf, fill),
        status=shelf.status.value if hasattr(shelf.status, "value") else shelf.status,
        inactive_reason=(
            shelf.inactive_reason.value
            if shelf.inactive_reason is not None and hasattr(shelf.inactive_reason, "value")
            else shelf.inactive_reason
        ),
        volume_m3=shelf.total_volume_m3,
        used_volume_m3=round(used_volume, 4),
        used_weight_kg=round(used_weight, 3),
        volume_fill_percent=fill.volume_fill_percent if fill is not None else 0.0,
        weight_fill_percent=fill.weight_fill_percent if fill is not None else 0.0,
        free_volume_m3=round(max(0.0, total_volume - used_volume), 4),
        free_weight_kg=round(max(0.0, total_weight - used_weight), 3),
        items_count=fill.items_count if fill is not None else 0,
        overloaded=fill.is_overloaded if fill is not None else False,
    )

@router.get(
    "/{warehouse_id}/racks",
    response_model=list[RackSummaryResponse],
    summary="Список стелажів складу",
)
async def list_racks(
    warehouse_id: int,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[RackSummaryResponse]:
    _check_warehouse_access(current_user, warehouse_id)
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    racks = await crud.get_racks_by_warehouse(session, warehouse_id)
    rack_fills = await fill_service.get_rack_fills(session, warehouse_id)
    return [_rack_to_summary(r, rack_fills.get(r.id)) for r in racks]

@router.get(
    "/{warehouse_id}/racks/{rack_code}",
    response_model=RackDetailsResponse,
    summary="Деталі стелажа з полицями",
)
async def get_rack(
    warehouse_id: int,
    rack_code: str,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> RackDetailsResponse:
    _check_warehouse_access(current_user, warehouse_id)
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стелаж не знайдено")
    rack_fills = await fill_service.get_rack_fills(session, warehouse_id)
    fill = rack_fills.get(rack.id)
    shelf_fills = fill.shelves if fill is not None else {}
    return RackDetailsResponse(
        rack_id=rack.id,
        rack_code=rack.code,
        zone_name=None,
        updated_at=None,
        shelves=[_shelf_to_info(s, shelf_fills.get(s.id)) for s in rack.shelves],
        volume_fill_percent=fill.volume_fill_percent if fill is not None else 0.0,
        weight_fill_percent=fill.weight_fill_percent if fill is not None else 0.0,
        used_volume_m3=round(float(fill.used_volume_m3), 4) if fill is not None else 0.0,
        total_volume_m3=round(float(fill.total_volume_m3), 4) if fill is not None else 0.0,
        used_weight_kg=round(float(fill.used_weight_kg), 3) if fill is not None else 0.0,
        total_max_weight_kg=(
            round(float(fill.total_max_weight_kg), 3) if fill is not None else 0.0
        ),
    )

@router.get(
    "/{warehouse_id}/racks/{rack_code}/shelves",
    response_model=list[ShelfResponse],
    summary="Отримати всі полиці стелажа",
)
async def list_shelves(
    warehouse_id: int,
    rack_code: str,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[ShelfResponse]:
    check_shelf_warehouse_access(current_user, warehouse_id)

    warehouse = await crud.get_warehouse(session, warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Склад не знайдено"
        )

    rack = await crud.get_rack_by_code(
        session, warehouse_id, rack_code
    )

    if rack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Стелаж не знайдено"
        )

    shelves = await crud.get_shelves_by_rack(session, rack.id)
    shelf_fills = await fill_service.get_shelf_fills(session, warehouse_id)

    return [_shelf_to_response(shelf, shelf_fills.get(shelf.id)) for shelf in shelves]

@router.post(
    "/{warehouse_id}/lpn_container",
    response_model=LpnContainerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Зареєструвати LPN-контейнер на складі"
)
async def register_lpn_container(
    warehouse_id: int,
    current_user: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> LpnContainerResponse:
    _check_warehouse_access(current_user, warehouse_id)

    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Склад не знайдено",
        )

    container = await create_lpn_container(session, warehouse_id=warehouse_id)
    await session.commit()

    return LpnContainerResponse(
        lpn_container_id=container.id,
        warehouse_id=container.warehouse_id,
        qr=container.qr,
    )

@router.get(
    "/{warehouse_id}/racks/{rack_code}/shelves/{shelf_id}",
    response_model=ShelfResponse,
    summary="Отримати полицю за ID",
)
async def get_shelf(
    warehouse_id: int,
    rack_code: str,
    shelf_id: int,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> ShelfResponse:
    check_shelf_warehouse_access(current_user, warehouse_id)

    warehouse = await crud.get_warehouse(session, warehouse_id)

    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Склад не знайдено",
        )

    rack = await crud.get_rack_by_code(
        session, warehouse_id, rack_code
    )

    if rack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Стелаж не знайдено",
        )

    shelf = await crud.get_shelf(session, shelf_id)

    if shelf is None or shelf.rack_id != rack.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Полицю не знайдено",
        )

    shelf_fills = await fill_service.get_shelf_fills(session, warehouse_id)
    return _shelf_to_response(shelf, shelf_fills.get(shelf.id))

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
    current_user: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> ShelfResponse:
    _check_warehouse_access(current_user, warehouse_id)
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
    current_user: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> ShelfResponse:
    _check_warehouse_access(current_user, warehouse_id)
    if data.model_dump(exclude_unset=True) == {}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    try:
        shelf = await crud.update_shelf(session, shelf, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = str(exc),
        )from exc
    # Нові розміри змінюють заповненість (аж до перевантаження) - віддаємо її одразу
    shelf_fills = await fill_service.get_shelf_fills(session, warehouse_id)
    return _shelf_to_response(shelf, shelf_fills.get(shelf.id))

@router.delete(
    "/{warehouse_id}/racks/{rack_code}/shelves/{shelf_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити полицю",
)
async def delete_shelf(
    warehouse_id: int,
    rack_code: str,
    shelf_id: int,
    current_user: dict = Depends(require_write),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    _check_warehouse_access(current_user, warehouse_id)
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Склад не знайдено")
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стелаж не знайдено")
    shelf = await crud.get_shelf(session, shelf_id)
    if shelf is None or shelf.rack_id != rack.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Полицю не знайдено")
    
    try:
        await crud.delete_shelf(session, shelf)
    except ValueError as exc:
        raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc


