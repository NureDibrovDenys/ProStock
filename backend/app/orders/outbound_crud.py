
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.enums import OrderStatus
from app.orders.models import OutboundOrder, OutboundOrderItem
from app.orders.schemas import OutboundOrderCreate, OutboundOrderUpdate
from app.products.models import Product, Recipient
from app.warehouses.models import Warehouse

class OutboundOrderNotFoundError(Exception):
    pass

class RecipientNotFoundError(Exception):
    pass

class ProductNotFoundError(Exception):
    pass

class WarehouseNotFoundError(Exception):
    pass

class InvoiceNumberAlreadyExistsError(Exception):
    pass

class OutboundOrderCannotBeDeletedError(Exception):
    pass


class OutboundOrderCannotBeEditedError(Exception):
    pass

def _default_options() -> list[LoaderOption]:
    return [
        joinedload(OutboundOrder.recipient, innerjoin=True),
        selectinload(OutboundOrder.items).selectinload(OutboundOrderItem.product),
    ]

async def get_outbound_order(
    session: AsyncSession,
    outbound_order_id: int,
    *,
    options: Sequence[LoaderOption] | None = None,
) -> OutboundOrder | None:
    
    if options is None:
        options = _default_options()
    return await session.scalar(
        select(OutboundOrder)
        .where(OutboundOrder.id == outbound_order_id)
        .options(*options)
        .execution_options(populate_existing=True)
    )

async def list_outbound_orders(
    session: AsyncSession,
    *,
    search: str | None = None,
    order_status: OrderStatus | None = None,
    recipient_id: int | None = None,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OutboundOrder], int]:
    
    conditions: list = []

    if recipient_id is not None:
        conditions.append(OutboundOrder.recipient_id == recipient_id)
    if warehouse_id is not None:
        conditions.append(OutboundOrder.warehouse_id == warehouse_id)
    if order_status is not None:
        conditions.append(OutboundOrder.order_status == order_status)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(or_(OutboundOrder.invoice_number.ilike(pattern)))

    total = await session.scalar(
        select(func.count(OutboundOrder.id)).where(*conditions)
    ) or 0

    result = await session.scalars(
        select(OutboundOrder)
        .options(*_default_options())
        .where(*conditions)
        .order_by(OutboundOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total

async def _ensure_products_exist(
    session: AsyncSession, product_ids: list[int]
) -> None:
    if not product_ids:
        return
    found = await session.scalars(select(Product.id).where(Product.id.in_(product_ids)))
    found_ids = set(found.all())
    missing = set(product_ids) - found_ids
    if missing:
        raise ProductNotFoundError(f"Product IDs {sorted(missing)} not found")

async def _ensure_warehouse_exists(session: AsyncSession, warehouse_id: int) -> None:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise WarehouseNotFoundError(f"Warehouse with ID {warehouse_id} not found")

async def create_outbound_order(
    session: AsyncSession,
    data: OutboundOrderCreate,
    created_by_user_id: int,
) -> OutboundOrder:
    
    recipient = await session.get(Recipient, data.recipient_id)
    if recipient is None:
        raise RecipientNotFoundError(f"Recipient with ID {data.recipient_id} not found")

    await _ensure_warehouse_exists(session, data.warehouse_id)
    await _ensure_products_exist(session, [item.product_id for item in data.items])

    order = OutboundOrder(
        recipient_id=data.recipient_id,
        warehouse_id=data.warehouse_id,
        invoice_number=data.invoice_number or f"TMP-{uuid.uuid4().hex}",
        planned_shipment_date=data.planned_shipment_date,
        order_status=OrderStatus.DRAFT,
        created_by_user_id=created_by_user_id,
    )
    session.add(order)

    try:
        await session.flush()
        if not data.invoice_number:
            order.invoice_number = f"ВН-{order.id:06d}"

        for item_data in data.items:
            session.add(
                OutboundOrderItem(
                    outbound_order_id=order.id,
                    product_id=item_data.product_id,
                    quantity=item_data.quantity,
                    package_type=item_data.package_type,
                )
            )

        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        original_error = getattr(e, "orig", None)
        if (
            original_error
            and getattr(original_error, "sqlstate", None) == "23505"
        ):
            raise InvoiceNumberAlreadyExistsError(
                f"Invoice number '{data.invoice_number}' already exists"
            ) from e
        raise

    created = await get_outbound_order(session, order.id)
    return created  # type: ignore[return-value]

async def update_outbound_order(
    session: AsyncSession,
    outbound_order: OutboundOrder,
    data: OutboundOrderUpdate,
) -> OutboundOrder:
    
    if outbound_order.order_status == OrderStatus.COMPLETED:
        raise OutboundOrderCannotBeEditedError(
            f"Накладну {outbound_order.invoice_number} не можна редагувати: "
            "она вже проведена (статус «Завершено»)"
        )

    if (
        "order_status" in data.model_dump(exclude_unset=True)
        and data.order_status == OrderStatus.DRAFT
        and outbound_order.order_status == OrderStatus.COMPLETED
    ):
        raise OutboundOrderCannotBeEditedError(
            f"Накладну {outbound_order.invoice_number} не можна повернути в чернетку: "
            "она вже проведена (статус «Завершено»)"
        )

    update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
    items_data: list[dict[str, Any]] | None = update_data.pop("items", None)

    if (
        "recipient_id" in update_data
        and update_data["recipient_id"] != outbound_order.recipient_id
    ):
        recipient = await session.get(Recipient, update_data["recipient_id"])
        if recipient is None:
            raise RecipientNotFoundError(
                f"Recipient with ID {update_data['recipient_id']} not found"
            )

    if (
        "warehouse_id" in update_data
        and update_data["warehouse_id"] != outbound_order.warehouse_id
    ):
        await _ensure_warehouse_exists(session, update_data["warehouse_id"])

    if (
        "invoice_number" in update_data
        and update_data["invoice_number"]
        and update_data["invoice_number"] != outbound_order.invoice_number
    ):
        existing = await session.scalar(
            select(OutboundOrder.id).where(
                OutboundOrder.invoice_number == update_data["invoice_number"],
                OutboundOrder.id != outbound_order.id,
            )
        )
        if existing is not None:
            raise InvoiceNumberAlreadyExistsError(
                f"Invoice number '{update_data['invoice_number']}' already exists"
            )

    for field, value in update_data.items():
        setattr(outbound_order, field, value)

    if items_data is not None:
        await _ensure_products_exist(
            session, [item["product_id"] for item in items_data]
        )
        outbound_order.items.clear()
        for item_data in items_data:
            session.add(
                OutboundOrderItem(
                    outbound_order_id=outbound_order.id,
                    product_id=item_data["product_id"],
                    quantity=item_data["quantity"],
                    package_type=item_data["package_type"],
                )
            )

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise InvoiceNumberAlreadyExistsError(
            "Data integrity error when updating an outbound invoice"
        ) from e

    updated = await get_outbound_order(session, outbound_order.id)
    return updated  # type: ignore[return-value]

async def delete_outbound_order(
    session: AsyncSession,
    outbound_order: OutboundOrder,
) -> None:
    
    if outbound_order.order_status not in (OrderStatus.DRAFT, OrderStatus.CANCELED):
        raise OutboundOrderCannotBeDeletedError(
            "Накладну не можна видалити: вона вже проведена або виконується"
        )

    try:
        await session.delete(outbound_order)
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise OutboundOrderCannotBeDeletedError(
            "Накладну не можна видалити - існують повʼязані записи"
        ) from e
