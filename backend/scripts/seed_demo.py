"""Наповнення демонстраційного каталогу товарів.

Ідемпотентний: наявні категорії та товари (за SKU) не дублюються.

    cd backend
    python -m scripts.seed_demo
"""
from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bootstrap import bootstrap
from app.core.db import async_session_maker
from app.core.enums import UnitOfMeasure
from app.products.models import Category, Product

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


async def seed() -> None:
    async with async_session_maker() as session:
        await bootstrap(session)

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
