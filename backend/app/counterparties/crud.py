from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SupplierStatus
from app.counterparties.schemas import SupplierCreate, SupplierUpdate
from app.products.models import Supplier


# Постачальники ──────────────────────────────────────────────────────────

async def list_suppliers(
    session: AsyncSession,
    search: str | None = None,
    status: SupplierStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Supplier], int]:
    conditions = []

    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Supplier.company_name).like(pattern),
                func.lower(Supplier.contact_person).like(pattern),
                func.lower(Supplier.email).like(pattern),
                Supplier.phone_number.like(pattern),
                Supplier.tax_id.like(pattern),
            )
        )
    if status is not None:
        conditions.append(Supplier.status == status)

    total = await session.scalar(
        select(func.count(Supplier.id)).where(*conditions)
    )

    result = await session.scalars(
        select(Supplier)
        .where(*conditions)
        .order_by(Supplier.company_name, Supplier.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total or 0


async def get_supplier(session: AsyncSession, supplier_id: int) -> Supplier | None:
    return await session.get(Supplier, supplier_id)


async def find_supplier_by_tax_id(
    session: AsyncSession, tax_id: str, exclude_id: int | None = None
) -> Supplier | None:
    query = select(Supplier).where(Supplier.tax_id == tax_id)
    if exclude_id is not None:
        query = query.where(Supplier.id != exclude_id)
    return await session.scalar(query)


async def create_supplier(session: AsyncSession, payload: SupplierCreate) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def update_supplier(
    session: AsyncSession, supplier: Supplier, payload: SupplierUpdate
) -> Supplier:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def delete_supplier(session: AsyncSession, supplier: Supplier) -> None:
    await session.delete(supplier)
    await session.commit()