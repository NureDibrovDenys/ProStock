"""CRUD-операції для товарів і категорій."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.enums import UnitOfMeasure
from app.products.models import Category, Product
from app.products.schemas import CategoryCreate, CategoryUpdate, ProductCreate, ProductUpdate


class SkuAlreadyExistsError(Exception):
    """Артикул уже зайнятий."""


class CategoryNotFoundError(Exception):
    """Категорію не знайдено."""


SORTABLE_FIELDS = {
    "sku_code": Product.sku_code,
    "name": Product.name,
    "weight": Product.weight,
    "min_stock_level": Product.min_stock_level,
    "product_id": Product.id,
}


# ── Категорії ──────────────────────────────────────────────────────────────

async def list_categories(session: AsyncSession) -> list[tuple[Category, int]]:
    """Категорії разом з кількістю товарів у кожній."""
    rows = await session.execute(
        select(Category, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name)
    )
    return [(category, count) for category, count in rows.all()]


async def get_category(session: AsyncSession, category_id: int) -> Category | None:
    return await session.get(Category, category_id)


async def find_category_by_name(session: AsyncSession, name: str) -> Category | None:
    return await session.scalar(
        select(Category).where(func.lower(Category.name) == name.strip().lower())
    )


async def create_category(session: AsyncSession, payload: CategoryCreate) -> Category:
    category = Category(name=payload.name, description=payload.description)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update_category(
    session: AsyncSession, category: Category, payload: CategoryUpdate
) -> Category:
    if payload.name is not None:
        category.name = payload.name
    if payload.description is not None:
        category.description = payload.description
    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(session: AsyncSession, category: Category) -> None:
    await session.delete(category)
    await session.commit()


async def count_products_in_category(session: AsyncSession, category_id: int) -> int:
    return await session.scalar(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    ) or 0


# ── Товари ─────────────────────────────────────────────────────────────────

def _base_query():
    return select(Product).options(joinedload(Product.category))


async def list_products(
    session: AsyncSession,
    *,
    search: str | None = None,
    category_id: int | None = None,
    unit_of_measure: UnitOfMeasure | None = None,
    sort_by: str = "product_id",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Product], int]:
    conditions = []

    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Product.sku_code).like(pattern),
                func.lower(Product.name).like(pattern),
            )
        )
    if category_id is not None:
        conditions.append(Product.category_id == category_id)
    if unit_of_measure is not None:
        conditions.append(Product.unit_of_measure == unit_of_measure)
    total = await session.scalar(select(func.count(Product.id)).where(*conditions)) or 0

    column = SORTABLE_FIELDS.get(sort_by, Product.id)
    order = desc(column) if sort_order.lower() == "desc" else asc(column)

    rows = (
        await session.scalars(
            _base_query()
            .where(*conditions)
            .order_by(order, Product.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return list(rows), total


async def iter_products(
    session: AsyncSession,
    *,
    search: str | None = None,
    category_id: int | None = None,
    unit_of_measure: UnitOfMeasure | None = None,
    sort_by: str = "product_id",
    sort_order: str = "asc",
) -> Iterable[Product]:
    """Усі товари за фільтром (для експорту)."""
    conditions = []
    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Product.sku_code).like(pattern),
                func.lower(Product.name).like(pattern),
            )
        )
    if category_id is not None:
        conditions.append(Product.category_id == category_id)
    if unit_of_measure is not None:
        conditions.append(Product.unit_of_measure == unit_of_measure)

    column = SORTABLE_FIELDS.get(sort_by, Product.id)
    order = desc(column) if sort_order.lower() == "desc" else asc(column)

    result = await session.scalars(_base_query().where(*conditions).order_by(order, Product.id))
    return result.all()


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.scalar(_base_query().where(Product.id == product_id))


async def get_product_by_sku(session: AsyncSession, sku_code: str) -> Product | None:
    return await session.scalar(_base_query().where(Product.sku_code == sku_code))


async def create_product(session: AsyncSession, payload: ProductCreate) -> Product:
    if await session.scalar(select(Product.id).where(Product.sku_code == payload.sku_code)):
        raise SkuAlreadyExistsError(payload.sku_code)

    if await session.get(Category, payload.category_id) is None:
        raise CategoryNotFoundError(str(payload.category_id))

    product = Product(
        sku_code=payload.sku_code,
        name=payload.name,
        category_id=payload.category_id,
        unit_of_measure=payload.unit_of_measure,
        width=payload.width,
        length=payload.length,
        height=payload.height,
        weight=payload.weight,
        min_stock_level=payload.min_stock_level,
    )
    session.add(product)
    await session.commit()
    return await get_product(session, product.id)  # type: ignore[return-value]


async def update_product(
    session: AsyncSession, product: Product, payload: ProductUpdate
) -> Product:
    data = payload.model_dump(exclude_unset=True)

    new_sku = data.get("sku_code")
    if new_sku is not None and new_sku != product.sku_code:
        exists = await session.scalar(
            select(Product.id).where(Product.sku_code == new_sku, Product.id != product.id)
        )
        if exists:
            raise SkuAlreadyExistsError(new_sku)
        product.sku_code = new_sku

    new_category_id = data.get("category_id")
    if new_category_id is not None and new_category_id != product.category_id:
        if await session.get(Category, new_category_id) is None:
            raise CategoryNotFoundError(str(new_category_id))
        product.category_id = new_category_id

    for field in ("name", "unit_of_measure", "width", "length", "height", "weight", "min_stock_level"):
        if field in data:
            setattr(product, field, data[field])

    await session.commit()
    return await get_product(session, product.id)  # type: ignore[return-value]


async def delete_product(session: AsyncSession, product: Product) -> None:
    await session.delete(product)
    await session.commit()
