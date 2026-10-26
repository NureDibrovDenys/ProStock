"""Запити до БД для складу, стелажів і дашборда."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ShelfStatus, UserStatus
from app.users.models import User
from app.warehouses.models import Rack, Shelf, Warehouse, Zone


async def get_warehouse(session: AsyncSession, warehouse_id: int) -> Warehouse | None:
    return await session.get(Warehouse, warehouse_id)


async def list_racks(session: AsyncSession, warehouse_id: int) -> list[Rack]:
    return list(
        (
            await session.scalars(
                select(Rack)
                .options(selectinload(Rack.shelves))
                .where(Rack.warehouse_id == warehouse_id)
                .order_by(Rack.code)
            )
        ).all()
    )


async def get_rack_by_code(
    session: AsyncSession, warehouse_id: int, rack_code: str
) -> Rack | None:
    return await session.scalar(
        select(Rack)
        .options(selectinload(Rack.shelves))
        .where(Rack.warehouse_id == warehouse_id, Rack.code == rack_code)
    )


async def list_zones(session: AsyncSession, warehouse_id: int) -> list[Zone]:
    return list(
        (await session.scalars(select(Zone).where(Zone.warehouse_id == warehouse_id))).all()
    )


def shelf_is_occupied(shelf: Shelf) -> bool:
    return shelf.is_occupied or shelf.status == ShelfStatus.OCCUPIED


def rack_fill_percent(rack: Rack) -> int:
    """Відсоток зайнятих полиць стелажа (0…100)."""
    shelves = rack.shelves or []
    total = len(shelves) or rack.shelves_count or 0
    if total <= 0:
        return 0
    occupied = sum(1 for shelf in shelves if shelf_is_occupied(shelf))
    return round(occupied / total * 100)


async def count_active_users(session: AsyncSession) -> int:
    return await session.scalar(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    ) or 0


def free_area_m2(warehouse: Warehouse, racks: list[Rack], zones: list[Zone]) -> float:
    """Вільна площа: загальна мінус проєкції стелажів і зон."""
    total = float(warehouse.total_area or 0)
    used = 0.0
    for rack in racks:
        used += float(rack.width or 0) * float(rack.length or 0)
    for zone in zones:
        used += float(zone.width or 0) * float(zone.length or 0)
    return max(0.0, round(total - used, 2))


def now() -> datetime:
    return datetime.now(timezone.utc)
