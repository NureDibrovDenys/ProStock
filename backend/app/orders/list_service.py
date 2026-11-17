
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, and_, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus, OrderType
from app.orders.models import InboundOrder, InboundOrderItem, OutboundOrder, OutboundOrderItem
from app.orders.schemas import OrderListItem
from app.products.models import Recipient, Supplier

def _inbound_query(
    order_status: OrderStatus | None,
    search: str | None,
    warehouse_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select:
    conditions = []
    if order_status is not None:
        conditions.append(InboundOrder.order_status == order_status)
    if warehouse_id is not None:
        conditions.append(InboundOrder.warehouse_id == warehouse_id)
    if date_from is not None:
        conditions.append(InboundOrder.expected_delivery_date >= date_from)
    if date_to is not None:
        conditions.append(InboundOrder.expected_delivery_date <= date_to)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                InboundOrder.invoice_number.ilike(pattern),
                Supplier.company_name.ilike(pattern),
            )
        )

    return (
        select(
            literal(OrderType.INBOUND.value).label("order_type"),
            InboundOrder.id.label("order_id"),
            InboundOrder.invoice_number.label("invoice_number"),
            InboundOrder.supplier_id.label("counterparty_id"),
            Supplier.company_name.label("counterparty_name"),
            InboundOrder.warehouse_id.label("warehouse_id"),
            InboundOrder.order_status.label("order_status"),
            InboundOrder.expected_delivery_date.label("date"),
            func.count(InboundOrderItem.id).label("items_count"),
            func.coalesce(func.sum(InboundOrderItem.quantity), 0).label("total_quantity"),
        )
        .join(Supplier, InboundOrder.supplier_id == Supplier.id)
        .outerjoin(InboundOrderItem, InboundOrderItem.inbound_order_id == InboundOrder.id)
        .where(and_(*conditions) if conditions else True)
        .group_by(
            InboundOrder.id,
            InboundOrder.invoice_number,
            InboundOrder.supplier_id,
            Supplier.company_name,
            InboundOrder.warehouse_id,
            InboundOrder.order_status,
            InboundOrder.expected_delivery_date,
        )
    )

def _outbound_query(
    order_status: OrderStatus | None,
    search: str | None,
    warehouse_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select:
    conditions = []
    if order_status is not None:
        conditions.append(OutboundOrder.order_status == order_status)
    if warehouse_id is not None:
        conditions.append(OutboundOrder.warehouse_id == warehouse_id)
    if date_from is not None:
        conditions.append(OutboundOrder.planned_shipment_date >= date_from)
    if date_to is not None:
        conditions.append(OutboundOrder.planned_shipment_date <= date_to)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                OutboundOrder.invoice_number.ilike(pattern),
                Recipient.company_name.ilike(pattern),
            )
        )

    return (
        select(
            literal(OrderType.OUTBOUND.value).label("order_type"),
            OutboundOrder.id.label("order_id"),
            OutboundOrder.invoice_number.label("invoice_number"),
            OutboundOrder.recipient_id.label("counterparty_id"),
            Recipient.company_name.label("counterparty_name"),
            OutboundOrder.warehouse_id.label("warehouse_id"),
            OutboundOrder.order_status.label("order_status"),
            OutboundOrder.planned_shipment_date.label("date"),
            func.count(OutboundOrderItem.id).label("items_count"),
            func.coalesce(func.sum(OutboundOrderItem.quantity), 0).label("total_quantity"),
        )
        .join(Recipient, OutboundOrder.recipient_id == Recipient.id)
        .outerjoin(
            OutboundOrderItem,
            OutboundOrderItem.outbound_order_id == OutboundOrder.id,
        )
        .where(and_(*conditions) if conditions else True)
        .group_by(
            OutboundOrder.id,
            OutboundOrder.invoice_number,
            OutboundOrder.recipient_id,
            Recipient.company_name,
            OutboundOrder.warehouse_id,
            OutboundOrder.order_status,
            OutboundOrder.planned_shipment_date,
        )
    )

def _to_status(value) -> OrderStatus:
    
    if isinstance(value, OrderStatus):
        return value
    try:
        return OrderStatus(value)
    except ValueError:
        return OrderStatus(str(value).lower())

def _to_order_type(value) -> OrderType:
    
    if isinstance(value, OrderType):
        return value
    try:
        return OrderType(value)
    except ValueError:
        return OrderType(str(value).lower())

async def list_orders(
    session: AsyncSession,
    *,
    order_type: OrderType | None = None,
    order_status: OrderStatus | None = None,
    search: str | None = None,
    warehouse_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OrderListItem], int]:
    
    queries = []
    if order_type in (None, OrderType.INBOUND):
        queries.append(
            _inbound_query(order_status, search, warehouse_id, date_from, date_to)
        )
    if order_type in (None, OrderType.OUTBOUND):
        queries.append(
            _outbound_query(order_status, search, warehouse_id, date_from, date_to)
        )

    if not queries:
        return [], 0

    combined = union_all(*queries).subquery()

    total = await session.scalar(
        select(func.count()).select_from(combined)
    ) or 0

    rows = (
        await session.execute(
            select(combined)
            .order_by(combined.c.date.desc(), combined.c.order_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        OrderListItem(
            order_type=_to_order_type(row.order_type),
            order_id=row.order_id,
            number=(
                f"ПН-{row.order_id:06d}"
                if row.order_type == OrderType.INBOUND.value
                else f"ВН-{row.order_id:06d}"
            ),
            invoice_number=row.invoice_number,
            counterparty_id=row.counterparty_id,
            counterparty_name=row.counterparty_name,
            warehouse_id=row.warehouse_id,
            order_status=_to_status(row.order_status),
            date=row.date,
            items_count=row.items_count,
            total_quantity=str(row.total_quantity),
        )
        for row in rows
    ]
    return items, total
