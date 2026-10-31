from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import RoleName
from app.core.rbac import ADMIN_ROLES, WAREHOUSE_MAP_WRITE_ROLES
from app.utils.security import get_current_user, require_roles
from ..schemas import WareHouseMapSchema, WarehouseMapUpdateSchema
from app.warehouses.services.warehouse_map_service import WarehouseMapNotFound, WarehouseMapService

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouse Map"])


def _not_found(warehouse_id: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Склад {warehouse_id} не знайдено")


def _check_warehouse_access(current_user: dict, warehouse_id: int) -> None:
    """Перевіряє, що користувач має право доступу до конкретного складу.

    Правила:
    - root / administrator — доступ до будь-якого складу.
    - warehouse_manager / storekeeper — лише до свого складу (warehouse_id у профілі).
      Якщо warehouse_id у профілі не заданий — доступ заборонено.
    """
    role = current_user.get("role", "")
    if role in ADMIN_ROLES:
        # Адміністратори не обмежені конкретним складом
        return

    user_warehouse = current_user.get("warehouse_id")
    if user_warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ваш обліковий запис не прив'язаний до жодного складу. Зверніться до адміністратора.",
        )
    if user_warehouse != warehouse_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ до цього складу заборонено.",
        )


@router.get(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
    dependencies=[Depends(get_current_user)],
)
async def get_warehouse_map(
    warehouse_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    _check_warehouse_access(current_user, warehouse_id)
    try:
        return await WarehouseMapService.get_map(session, warehouse_id)
    except WarehouseMapNotFound:
        raise _not_found(warehouse_id)


# відповідь — збережена мапа з id нових об'єктів (фронт кладе її у кеш замість надісланої)
@router.put(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
    dependencies=[Depends(require_roles(*WAREHOUSE_MAP_WRITE_ROLES))],
)
async def save_warehouse_map(
    warehouse_id: int,
    map_data: WarehouseMapUpdateSchema,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    _check_warehouse_access(current_user, warehouse_id)
    try:
        return await WarehouseMapService.save_map(session, warehouse_id, map_data)
    except WarehouseMapNotFound:
        raise _not_found(warehouse_id)
