"""Наповнення демонстраційного каталогу товарів.

Ідемпотентний: наявні категорії та товари (за SKU) не дублюються.

    cd backend
    python -m scripts.seed_demo
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bootstrap import bootstrap
from app.core.db import async_session_maker
from app.core.enums import (
    PointType,
    ShelfStatus,
    UnitOfMeasure,
    ZoneType,
)
from app.products.models import Category, Product
from app.warehouses.models import (
    Rack,
    Shelf,
    Warehouse,
    WarehouseEntryPoint,
    WarehouseMapSnapshot,
    WarehouseWall,
    Zone,
)
from app.warehouses.services.warehouse_map_service import MAP_KEYS, WarehouseMapService

CATEGORIES: dict[str, str] = {
    "Побутова хімія": "Засоби для прибирання та догляду",
    "Бакалія": "Продукти тривалого зберігання",
    "Електроніка": "Дрібна побутова техніка",
}

# sku, назва, категорія, одиниця, ширина, довжина, висота, вага, мін. залишок
PRODUCTS: list[tuple[str, str, str, UnitOfMeasure, str, str, str, str, str]] = [
    ("CHEM-001", "Мило рідке, 1 л", "Побутова хімія", UnitOfMeasure.PCS, "0.10", "0.10", "0.25", "1.05", "25"),
    ("CHEM-002", "Засіб для скла, 500 мл", "Побутова хімія", UnitOfMeasure.PCS, "0.08", "0.08", "0.22", "0.55", "15"),
    ("CHEM-003", "Порошок пральний, 3 кг", "Побутова хімія", UnitOfMeasure.BOX, "0.30", "0.18", "0.10", "3.20", "10"),
    ("FOOD-001", "Цукор білий, 1 кг", "Бакалія", UnitOfMeasure.KG, "0.12", "0.18", "0.05", "1.00", "40"),
    ("FOOD-002", "Борошно пшеничне, 2 кг", "Бакалія", UnitOfMeasure.KG, "0.16", "0.24", "0.08", "2.00", "30"),
    ("FOOD-003", "Олія соняшникова, 1 л", "Бакалія", UnitOfMeasure.PCS, "0.09", "0.09", "0.27", "0.92", "20"),
    ("ELEC-001", "Лампа LED, 9 Вт", "Електроніка", UnitOfMeasure.PCS, "0.06", "0.06", "0.11", "0.08", "50"),
    ("ELEC-002", "Подовжувач 3 м", "Електроніка", UnitOfMeasure.PCS, "0.20", "0.20", "0.06", "0.45", "12"),
    ("ELEC-003", "Батарейка AA, 4 шт", "Електроніка", UnitOfMeasure.BOX, "0.08", "0.12", "0.02", "0.10", "60"),
]


async def _get_or_create_category(session: AsyncSession, name: str, description: str) -> Category:
    category = await session.scalar(select(Category).where(func.lower(Category.name) == name.lower()))
    if category is None:
        category = Category(name=name, description=description)
        session.add(category)
        await session.flush()
        print(f"  + категорія {name}")
    return category


async def seed_warehouse(session: AsyncSession) -> None:
    """Демо-склад із стелажами, полицями та зонами (ідемпотентно)."""
    warehouse = await session.scalar(select(Warehouse).order_by(Warehouse.id))
    if warehouse is None:
        warehouse = Warehouse(
            name="А-01",
            address="Київ, вул. Складська, 1",
            total_area=Decimal("1000.00"),
        )
        session.add(warehouse)
        await session.flush()
        print("  + склад Склад №1")

    existing_racks = await session.scalar(
        select(func.count(Rack.id)).where(Rack.warehouse_id == warehouse.id)
    )
    if not existing_racks:
        presets = [
            ("R-1", 12, 8, "1.10", "2.70", 4),
            ("R-2", 18, 8, "1.10", "2.70", 4),
            ("R-3", 24, 8, "1.10", "2.70", 4),
        ]
        for code, x, y, width, length, shelves_count in presets:
            rack = Rack(
                warehouse_id=warehouse.id,
                code=code,
                x=Decimal(x),
                y=Decimal(y),
                width=Decimal(width),
                length=Decimal(length),
                rotation_angle=Decimal("0"),
                shelves_count=shelves_count,
            )
            session.add(rack)
            await session.flush()
            for level in range(1, shelves_count + 1):
                occupied = level <= 2
                session.add(
                    Shelf(
                        rack_id=rack.id,
                        code=f"{code}-{level}",
                        qr=f"PROSTOCK:{code}-{level}",
                        width=Decimal("1.00"),
                        length=Decimal("1.00"),
                        height=Decimal("0.40"),
                        max_weight=Decimal("120.000"),
                        is_occupied=occupied,
                        status=ShelfStatus.OCCUPIED if occupied else ShelfStatus.ACTIVE,
                    )
                )
        print("  + 3 стелажі з полицями")

    existing_zones = await session.scalar(
        select(func.count(Zone.id)).where(Zone.warehouse_id == warehouse.id)
    )
    if not existing_zones:
        session.add_all(
            [
                Zone(
                    warehouse_id=warehouse.id,
                    name="Зона приймання",
                    type=ZoneType.INBOUND_DOCK,
                    x=Decimal("4"),
                    y=Decimal("3"),
                    width=Decimal("6"),
                    length=Decimal("8"),
                ),
                Zone(
                    warehouse_id=warehouse.id,
                    name="Зона зберігання",
                    type=ZoneType.STORAGE_AREA,
                    x=Decimal("17"),
                    y=Decimal("11"),
                    width=Decimal("10"),
                    length=Decimal("20"),
                ),
                Zone(
                    warehouse_id=warehouse.id,
                    name="Зона відвантаження",
                    type=ZoneType.OUTBOUND_DOCK,
                    x=Decimal("34"),
                    y=Decimal("3"),
                    width=Decimal("6"),
                    length=Decimal("8"),
                ),
            ]
        )
        print("  + 3 зони")

    existing_points = await session.scalar(
        select(func.count(WarehouseEntryPoint.id)).where(
            WarehouseEntryPoint.warehouse_id == warehouse.id
        )
    )
    if not existing_points:
        session.add(
            WarehouseEntryPoint(
                warehouse_id=warehouse.id,
                point_name="Головний вхід",
                point_type=PointType.GENERAL_ENTRY,
                x=Decimal("0"),
                y=Decimal("10"),
            )
        )
        print("  + точка входу")

    existing_walls = await session.scalar(
        select(func.count(WarehouseWall.id)).where(
            WarehouseWall.warehouse_id == warehouse.id
        )
    )
    if not existing_walls:
        for order, (x, y) in enumerate(
            [(0, 0), (40, 0), (40, 20), (0, 20)], start=1
        ):
            session.add(
                WarehouseWall(
                    warehouse_id=warehouse.id,
                    vertex_order=order,
                    x=Decimal(x),
                    y=Decimal(y),
                )
            )
        print("  + контур складу (4 вершини)")

    await session.flush()
    snapshot = await session.scalar(
        select(WarehouseMapSnapshot).where(
            WarehouseMapSnapshot.warehouse_id == warehouse.id
        )
    )
    if snapshot is None:
        payload = await WarehouseMapService.get_map(session, warehouse.id)
        await WarehouseMapService.save_map(
            session, warehouse.id, payload, provided_fields=set(MAP_KEYS)
        )
        print("  + топологію складу збережено")


async def seed() -> None:
    async with async_session_maker() as session:
        await bootstrap(session)
        await seed_warehouse(session)

        categories = {
            name: await _get_or_create_category(session, name, description)
            for name, description in CATEGORIES.items()
        }

        created = 0
        for sku, name, category_name, unit, width, length, height, weight, min_stock in PRODUCTS:
            exists = await session.scalar(select(Product.id).where(Product.sku_code == sku))
            if exists:
                continue
            session.add(
                Product(
                    sku_code=sku,
                    name=name,
                    category_id=categories[category_name].id,
                    unit_of_measure=unit,
                    width=width,
                    length=length,
                    height=height,
                    weight=weight,
                    min_stock_level=min_stock,
                )
            )
            created += 1

        await session.commit()
        total = await session.scalar(select(func.count(Product.id)))
        print(f"Готово: додано {created} товарів, усього в каталозі {total}.")


if __name__ == "__main__":
    asyncio.run(seed())
