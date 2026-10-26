from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.utils.security import ROOT,ADMIN, WAREHOUSE_MANAGER, get_current_user, require_roles
from ..schemas import WareHouseMapSchema, WarehouseMapUpdateSchema
from app.warehouses.services.warehouse_map_service import WarehouseMapNotFound, WarehouseMapService

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouse Map"])


def _not_found(warehouse_id: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Склад {warehouse_id} не знайдено")


@router.get(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
    dependencies=[Depends(get_current_user)],
)
async def get_warehouse_map(warehouse_id: int, session: AsyncSession = Depends(get_async_session)):
    try:
        return await WarehouseMapService.get_map(session, warehouse_id)
    except WarehouseMapNotFound:
        raise _not_found(warehouse_id)

#відповідь — збережена мапа з id нових об'єктів (фронт кладе її у кеш замість надісланої)
@router.put(
    "/{warehouse_id}/map",
    response_model=WareHouseMapSchema,
    dependencies=[Depends(require_roles(ROOT, ADMIN, WAREHOUSE_MANAGER))],
)
async def save_warehouse_map(
    warehouse_id: int,
    map_data: WarehouseMapUpdateSchema,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        return await WarehouseMapService.save_map(session, warehouse_id, map_data)
    except WarehouseMapNotFound:
        raise _not_found(warehouse_id)
