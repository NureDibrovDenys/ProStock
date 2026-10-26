"""Топологія складу: читання та збереження мапи конструктора."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.rbac import PRODUCT_WRITE_ROLES
from app.utils.security import get_current_user, require_roles
from app.warehouses import crud
from app.warehouses.schemas import WarehouseMapSchema
from app.warehouses.services.warehouse_map_service import WarehouseMapService

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouse Map"])

write_guard = Depends(require_roles(*PRODUCT_WRITE_ROLES))


async def _require_warehouse(session: AsyncSession, warehouse_id: int) -> None:
    if await crud.get_warehouse(session, warehouse_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Склад не знайдено",
        )


@router.get(
    "/{warehouse_id}/map",
    response_model=WarehouseMapSchema,
    dependencies=[Depends(get_current_user)],
)
async def get_warehouse_map(
    warehouse_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    await _require_warehouse(session, warehouse_id)
    return await WarehouseMapService.get_map(session, warehouse_id)


@router.put(
    "/{warehouse_id}/map",
    response_model=WarehouseMapSchema,
    dependencies=[write_guard],
)
async def save_warehouse_map(
    warehouse_id: int,
    map_data: WarehouseMapSchema,
    session: AsyncSession = Depends(get_async_session),
):
    await _require_warehouse(session, warehouse_id)
    saved = await WarehouseMapService.save_map(
        session,
        warehouse_id,
        map_data.model_dump(mode="json"),
        provided_fields=map_data.model_fields_set,
    )
    return saved
