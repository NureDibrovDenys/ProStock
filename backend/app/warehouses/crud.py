"""
CRUD-операції для складів.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.warehouses.models import Warehouse
from app.warehouses.schemas import WarehouseCreate, WarehouseUpdate


async def get_warehouse(session: AsyncSession, warehouse_id: int) -> Warehouse | None:
    """Повертає склад за id або None."""
    return await session.scalar(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    )


async def list_warehouses(session: AsyncSession) -> list[Warehouse]:
    """Повертає всі склади, відсортовані за id."""
    result = await session.scalars(select(Warehouse).order_by(Warehouse.id))
    return list(result.all())


async def create_warehouse(session: AsyncSession, data: WarehouseCreate) -> Warehouse:
    """Створює новий склад і повертає його."""
    warehouse = Warehouse(
        name=data.name,
        address=data.address,
        total_area=data.total_area,
    )
    session.add(warehouse)
    await session.commit()
    await session.refresh(warehouse)
    return warehouse


async def update_warehouse(
    session: AsyncSession,
    warehouse: Warehouse,
    data: WarehouseUpdate,
) -> Warehouse:
    """
    Частково оновлює склад.
    Змінює лише ті поля, що явно передані в тілі запиту (не None).
    """
    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(warehouse, field, value)
    await session.commit()
    await session.refresh(warehouse)
    return warehouse


async def delete_warehouse(session: AsyncSession, warehouse: Warehouse) -> None:
    """Видаляє склад разом із усіма пов'язаними сутностями."""
    await session.delete(warehouse)
    await session.commit()
