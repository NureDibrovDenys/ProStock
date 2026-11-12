"""
CRUD operations for inbound orders
"""
from __future__ import annotations

from typing import Any

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.enums import OrderStatus
from app.orders.models import InboundOrder, InboundOrderItem
from app.orders.schemas import (
    InboundOrderUpdate,
    InboundOrderCreate
)
from app.products.models import Product, Supplier


class InboundOrderNotFoundError(Exception):
    pass

class SupplierNotFoundError(Exception):
    pass

class ProductNotFoundError(Exception):
    pass

class InvoiceNumberAlreadyExistsError(Exception):
    pass

class InboundOrderCannotBeDeletedError(Exception):
    pass

async def get_inbound_order(
    session: AsyncSession,
    inbound_order_id: int,
    *,
    options: Sequence[LoaderOption] | None = None,
) -> InboundOrder:
    """
    Returns the incoming invoice by ID,
    along with the supplier and line items, or None.
    """
    if options is None:
        options = [
            joinedload(
                InboundOrder.supplier,
                innerjoin=True
            ),
            selectinload(
                InboundOrder.items
            ).selectinload(
                InboundOrderItem.product
            ),
        ]
    
    inbound_order: InboundOrder | None = await session.scalar(
        select(InboundOrder)
        .where(InboundOrder.id == inbound_order_id)
        .options(*options)
    )
    return inbound_order

async def list_inbound_orders(
    session: AsyncSession,
    *,
    search: str | None = None,
    order_status: OrderStatus | None = None,
    supplier_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[InboundOrder], int]:
    """
    Returns a page of incoming invoices and the total count.
    """
    conditions: list = []
    
    if supplier_id is not None:
        conditions.append(InboundOrder.supplier_id == supplier_id)
    if order_status is not None:
        conditions.append(InboundOrder.order_status == order_status)
    
    if search and search.strip():
        pattern: str = f"%{search.strip()}%"
        conditions.append(
            or_(InboundOrder.invoice_number.ilike(pattern))
        )
    
    count_stmt = select(
        func.count(InboundOrder.id)
        .where(*conditions)
    )
    count_result = await session.scalar(count_stmt)
    total: int = count_result or 0
    
    orders_stmt = (
        select(InboundOrder)
        .options(
            joinedload(InboundOrder.supplier),
            selectinload(
                InboundOrder.items
            ).selectinload(
                InboundOrderItem.product
            )
        )
        .where(*conditions)
        .order_by(InboundOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    result = await session.scalars(orders_stmt)
    return list(result.all()), total

async def create_inbound_order(
    session: AsyncSession,
    data: InboundOrderCreate,
    created_by_user_id: int,
) -> InboundOrder:
    """
    Creates a new incoming invoice along with the line items.
    """
    supplier: Supplier | None = await session.get(
        Supplier, data.supplier_id
    )
    if supplier is None:
        raise SupplierNotFoundError(
            f"Supplier with ID {data.supplier_id} not found"
        )
    
    product_ids: list[int] = [item.product_id for item in data.items]
    if product_ids:
        found_products = await session.scalars(
            select(Product.id)
            .where(Product.id.in_(product_ids))
        )
        found_ids = set(found_products.all())
        missing_ids = set(product_ids) - found_ids
        if missing_ids:
            raise ProductNotFoundError(
                f"Product IDs {missing_ids} not found"
            )
    
    inbound_order: InboundOrder = InboundOrder(
        supplier_id=data.supplier_id,
        invoice_number=data.invoice_number,
        expected_delivery_date=data.expected_delivery_date,
        order_status=data.order_status,
        created_by_user_id=created_by_user_id,
    )
    session.add(inbound_order)
    
    try:
        await session.flush()
        
        for item_data in data.items:
            item: InboundOrderItem = InboundOrderItem(
                inbound_order_id=inbound_order.id,
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                package_type=item_data.package_type,
            )
            session.add(item)
        
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        
        # Check if this specifically a uniqueness violation for
        # invoice number (code 23505 for PostgresSQL)
        original_error = getattr(e, "original_error", None)
        if (
            original_error
            and getattr(original_error, "original_name", None) == "23505"
        ):
            raise InvoiceNumberAlreadyExistsError(
                f"Invoice number '{inbound_order.invoice_number}' already exists"
            ) from e
        raise
        
    created_inbound_order: InboundOrder = await get_inbound_order(
        session, inbound_order.id
    )
    return created_inbound_order

async def update_inbound_order(
    session: AsyncSession,
    inbound_order: InboundOrder,
    data: InboundOrderUpdate,
) -> InboundOrder:
    """
    Partially updates the incoming invoice and its line items.
    """
    update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
    items_data: list[dict[str, Any]] | None = update_data.pop("items", None)
    
    if (
        "supplier_id" in update_data
        and update_data["supplier_id"] != inbound_order.supplier_id
    ):
        supplier: Supplier | None = await session.get(
            Supplier, update_data["supplier_id"]
        )
        if supplier is None:
            raise SupplierNotFoundError(
                f"Supplier with ID {update_data['supplier_id']} not found"
            )
        
    if (
        "invoice_number" in update_data
        and update_data["invoice_number"] != inbound_order.invoice_number
    ):
        existing = await session.scalar(
            select(InboundOrder.id)
            .where(
                InboundOrder.invoice_number == update_data["invoice_number"],
                InboundOrder.id != inbound_order.id,
            )
        )
        if existing is not None:
            raise InvoiceNumberAlreadyExistsError(
                f"Invoice number '{update_data['invoice_number']}' already exists"
            )
        
    for field, value in update_data.items():
        setattr(inbound_order, field, value)
    
    if items_data is not None:
        product_ids = [item.product_id for item in items_data]
        if product_ids:
            found_products = await session.scalars(
                select(Product.id)
                .where(Product.id.in_(product_ids))
            )
            found_ids = set(found_products.all())
            missing_ids = set(product_ids) - found_ids
            if missing_ids:
                raise ProductNotFoundError(
                    f"Products IDs {missing_ids} not found"
                )
        
        inbound_order.items.clear()
        for item_data in items_data:
            item: InboundOrderItem = InboundOrderItem(
                inbound_order_id=inbound_order.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                package_type=item_data["package_type"],
            )
            session.add(item)
        
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise InvoiceNumberAlreadyExistsError(
            "Data integrity error when updating an inbound invoice"
        ) from e
    updated_inbound_order: InboundOrder = await get_inbound_order(
        session, inbound_order.id
    )
    return updated_inbound_order

async def delete_inbound_order(
    session: AsyncSession,
    inbound_order: InboundOrder,
) -> None:
    """
    Deletes the incoming invoice
    (only if its status is DRAFT or CANCELLED).
    """
    if (
        inbound_order.order_status not in (
            OrderStatus.DRAFT, OrderStatus.CANCELED
        )
    ):
        raise InboundOrderCannotBeDeletedError(
            "It is not possible to delete inbound order "
            "that is already being processed or has been completed"
        )
    
    try:
        await session.delete(inbound_order)
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise InboundOrderCannotBeDeletedError(
            "The invoice cannot be deleted "
            "due to the existence of relates records"
        ) from e