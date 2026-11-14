"""
CRUD-операції для складів, стелажів і полиць.
"""
from __future__ import annotations

from decimal import Decimal
from wsgiref import validate

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.enums import ShelfStatus, InactiveReason
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
    Змінює лише ті поля, що явно передані в тілі запиту.
    Явний null для адреси стирає її (name і total_area null не приймають — див. WarehouseUpdate).
    """
    update_data = data.model_dump(exclude_unset=True)
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


def validate_shelf_status(
    shelf_status: ShelfStatus,
    inactive_reason: InactiveReason | None
)-> None:
    """Перевірка узгодженості статусу полиці та причини недоступності"""
    if shelf_status == ShelfStatus.OCCUPIED:
        raise ValueError("Статус 'occupied' не можна встановлювати вручну. Зайнятість полиці визначається складськими операціями.")
    
    if shelf_status == ShelfStatus.INACTIVE:
        if inactive_reason is None:
            raise ValueError ("Для неактивної полиці необхідно вказати причину недоступності.")
        
    elif inactive_reason is not None:
        raise ValueError ("Причину недоступності можна вказувати лише для неактивної полиці.")

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
    validate_shelf_status(data.status, data.inactive_reason)
    existing = await get_shelf_by_code(session, rack.id, data.code)
    if existing is not None:
        raise ValueError(f"Полиця з кодом '{data.code}' вже існує в стелажі '{rack.code}'")

    qr = f"R{rack.code}-{data.code}"
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
    update_data = data.model_dump(exclude_unset=True)
    new_status = update_data.get("status", shelf.status)
    new_reason = update_data.get("inactive_reason", shelf.inactive_reason)
    validate_shelf_status(new_status, new_reason)
    
    for field, value in update_data.items():
        setattr(shelf, field, value)
    await session.commit()
    await session.refresh(shelf)
    return shelf


async def delete_shelf(session: AsyncSession, shelf: Shelf) -> None:
    """Видаляє полицю."""
    
    if shelf.is_occupied:
        raise ValueError("Неможливо видалити зайняту полицю")
    await session.delete(shelf)
    await session.commit()
