from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.warehouses.models import Warehouse
from app.utils.security import get_current_user

router = APIRouter(prefix="/api/v1/warehouses", tags=["Warehouses"])


class WarehouseListItem(BaseModel):
    warehouse_id: int
    warehouse_name: str
    warehouse_address: str | None
    total_warehouse_area: float


@router.get("/{warehouse_id}", response_model=WarehouseListItem)
async def get_warehouse(
    warehouse_id: int,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    warehouse = await session.scalar(select(Warehouse).where(Warehouse.id == warehouse_id))
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не знайдено")
    return WarehouseListItem(
        warehouse_id=warehouse.id,
        warehouse_name=warehouse.name,
        warehouse_address=warehouse.address,
        total_warehouse_area=float(warehouse.total_area),
    )


@router.get("", response_model=list[WarehouseListItem])
async def list_warehouses(
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    warehouses = (await session.scalars(select(Warehouse).order_by(Warehouse.id))).all()
    return [
        WarehouseListItem(
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            warehouse_address=warehouse.address,
            total_warehouse_area=float(warehouse.total_area),
        )
        for warehouse in warehouses
    ]