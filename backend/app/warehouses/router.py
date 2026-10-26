"""Ендпоінти складу: картка, стелажі, дашборд."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.utils.security import get_current_user
from app.warehouses import crud
from app.warehouses.schemas import (
    DashboardStatsSchema,
    RackDetailsSchema,
    RackFillSchema,
    RackSummarySchema,
    ShelfInfoSchema,
    WarehouseRead,
)

router = APIRouter(
    prefix="/api/v1/warehouses",
    tags=["Warehouses"],
    dependencies=[Depends(get_current_user)],
)


async def _require_warehouse(session: AsyncSession, warehouse_id: int):
    warehouse = await crud.get_warehouse(session, warehouse_id)
    if warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Склад не знайдено",
        )
    return warehouse


@router.get("/{warehouse_id}", response_model=WarehouseRead)
async def get_warehouse(
    warehouse_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    warehouse = await _require_warehouse(session, warehouse_id)
    return WarehouseRead(
        warehouse_id=warehouse.id,
        warehouse_name=warehouse.name,
        warehouse_address=warehouse.address,
        total_warehouse_area=float(warehouse.total_area),
    )


@router.get("/{warehouse_id}/racks", response_model=list[RackSummarySchema])
async def list_racks(
    warehouse_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    await _require_warehouse(session, warehouse_id)
    racks = await crud.list_racks(session, warehouse_id)
    return [
        RackSummarySchema(
            rack_id=rack.id,
            rack_code=rack.code,
            shelves_count=len(rack.shelves) or rack.shelves_count,
            fill_percent=crud.rack_fill_percent(rack),
        )
        for rack in racks
    ]


@router.get("/{warehouse_id}/racks/{rack_code}", response_model=RackDetailsSchema)
async def get_rack(
    warehouse_id: int,
    rack_code: str,
    session: AsyncSession = Depends(get_async_session),
):
    await _require_warehouse(session, warehouse_id)
    rack = await crud.get_rack_by_code(session, warehouse_id, rack_code)
    if rack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Стелаж {rack_code} не знайдено",
        )

    shelves = sorted(rack.shelves or [], key=lambda shelf: shelf.code)
    return RackDetailsSchema(
        rack_id=rack.id,
        rack_code=rack.code,
        zone_name=None,
        updated_at=crud.now(),
        shelves=[
            ShelfInfoSchema(
                shelf_id=shelf.id,
                shelf_code=shelf.code,
                product_name=None,
                occupied=1 if crud.shelf_is_occupied(shelf) else 0,
                capacity=1,
                shelf_status=shelf.status.value,
            )
            for shelf in shelves
        ],
    )


@router.get("/{warehouse_id}/dashboard", response_model=DashboardStatsSchema)
async def get_dashboard(
    warehouse_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    warehouse = await _require_warehouse(session, warehouse_id)
    racks = await crud.list_racks(session, warehouse_id)
    zones = await crud.list_zones(session, warehouse_id)
    employees_total = await crud.count_active_users(session)

    total_shelves = sum(len(rack.shelves) or rack.shelves_count for rack in racks)
    occupied_shelves = sum(
        1
        for rack in racks
        for shelf in (rack.shelves or [])
        if crud.shelf_is_occupied(shelf)
    )
    fill_percent = round(occupied_shelves / total_shelves * 100) if total_shelves else 0

    return DashboardStatsSchema(
        racks_count=len(racks),
        zones_count=len(zones),
        fill_percent=fill_percent,
        fill_change_week=0,
        on_shift=0,
        employees_total=employees_total,
        free_area_m2=crud.free_area_m2(warehouse, racks, zones),
        total_area_m2=float(warehouse.total_area),
        updated_at=crud.now(),
        rack_fill=[
            RackFillSchema(
                rack_id=rack.id,
                rack_code=rack.code,
                fill_percent=crud.rack_fill_percent(rack),
            )
            for rack in racks
        ],
        recent_operations=[],
    )
