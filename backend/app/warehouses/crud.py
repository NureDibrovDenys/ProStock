"""
CRUD-операції для складів, стелажів і полиць.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.warehouses.models import Rack, Shelf, Warehouse
from app.warehouses.schemas import ShelfCreate, ShelfUpdate, WarehouseCreate, WarehouseUpdate


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


# ── Rack ──────────────────────────────────────────────────────────────────────

async def get_racks_by_warehouse(
    session: AsyncSession,
    warehouse_id: int,
) -> list[Rack]:
    """Повертає всі стелажі складу з їхніми полицями, відсортовані за кодом."""
    result = await session.scalars(
        select(Rack)
        .where(Rack.warehouse_id == warehouse_id)
        .options(selectinload(Rack.shelves))
        .order_by(Rack.code)
    )
    return list(result.all())


async def get_rack_by_code(
    session: AsyncSession,
    warehouse_id: int,
    rack_code: str,
) -> Rack | None:
    """Повертає стелаж за кодом і id складу (разом із полицями) або None."""
    return await session.scalar(
        select(Rack)
        .where(Rack.warehouse_id == warehouse_id, Rack.code == rack_code)
        .options(selectinload(Rack.shelves))
    )


# ── Shelf ─────────────────────────────────────────────────────────────────────
#повертає всі полиці конкретного стелажа
async def get_shelves_by_rack(
    session: AsyncSession,
    rack_id:int,
    
)-> list[Shelf]:
    result = await session.scalars(
        select(Shelf).where(Shelf.rack_id == rack_id).order_by(Shelf.code)
        
    )
    return list(result.all())


async def get_shelf(session: AsyncSession, shelf_id: int) -> Shelf | None:
    """Повертає полицю за id або None."""
    return await session.scalar(select(Shelf).where(Shelf.id == shelf_id))


async def get_shelf_by_code(
    session: AsyncSession,
    rack_id: int,
    shelf_code: str,
) -> Shelf | None:
    """Повертає полицю за кодом у межах стелажа або None."""
    return await session.scalar(
        select(Shelf).where(Shelf.rack_id == rack_id, Shelf.code == shelf_code)
    )


async def create_shelf(
    session: AsyncSession,
    rack: Rack,
    data: ShelfCreate,
) -> Shelf:
    """
    Створює нову полицю для стелажа.

    QR формується як «{rack.code}-{data.code}».
    Перевіряє унікальність code в рамках БД; при конфлікті — raises ValueError.
    """
    existing = await get_shelf_by_code(session, rack.id, data.code)
    if existing is not None:
        raise ValueError(f"Полиця з кодом '{data.code}' вже існує в стелажі '{rack.code}'")

    qr = f"{rack.code}-{data.code}"
    shelf = Shelf(
        rack_id=rack.id,
        code=data.code,
        qr=qr,
        width=data.width,
        length=data.length,
        height=data.height,
        max_weight=data.max_weight,
        status=data.status,
        inactive_reason=data.inactive_reason,
    )
    session.add(shelf)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(
            f"Полиця з кодом '{data.code}' або QR '{qr}' вже існує"
        )
    await session.refresh(shelf)
    return shelf


async def update_shelf(
    session: AsyncSession,
    shelf: Shelf,
    data: ShelfUpdate,
) -> Shelf:
    """Частково оновлює полицю — лише передані (не None) поля."""
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(shelf, field, value)
    await session.commit()
    await session.refresh(shelf)
    return shelf


async def delete_shelf(session: AsyncSession, shelf: Shelf) -> None:
    """Видаляє полицю."""
    await session.delete(shelf)
    await session.commit()
