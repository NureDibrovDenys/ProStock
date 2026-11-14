
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.orders.models import InboundOrder, OutboundOrder
from app.stock import service as stock_service

class OrderCannotBePostedError(Exception):
    pass

def _ensure_draft(order_status: OrderStatus, invoice_number: str) -> None:
    if order_status != OrderStatus.DRAFT:
        raise OrderCannotBePostedError(
            f"Накладну {invoice_number} не можна провести: "
            f"статус «{order_status.value}» (провести можна лише чернетку)"
        )

async def post_inbound_order(
    session: AsyncSession,
    order: InboundOrder,
    user_id: int,
) -> InboundOrder:
    
    _ensure_draft(order.order_status, order.invoice_number)

    items = [
        (item.product_id, Decimal(str(item.quantity)), item.package_type)
        for item in order.items
    ]
    if not items:
        raise OrderCannotBePostedError("Накладна без позицій не може бути проведена")

    shortages = await stock_service.place_incoming(
        session,
        order.warehouse_id,
        items,
        user_id=user_id,
        order_id=order.id,
    )
    if shortages:
        raise stock_service.InsufficientCapacityError(shortages)

    order.order_status = OrderStatus.COMPLETED
    await session.commit()
    return order

async def post_outbound_order(
    session: AsyncSession,
    order: OutboundOrder,
    user_id: int,
) -> OutboundOrder:
    
    _ensure_draft(order.order_status, order.invoice_number)

    items = [
        (item.product_id, Decimal(str(item.quantity)), item.package_type)
        for item in order.items
    ]
    if not items:
        raise OrderCannotBePostedError("Накладна без позицій не може бути проведена")

    await stock_service.remove_outgoing(
        session,
        order.warehouse_id,
        items,
        user_id=user_id,
        order_id=order.id,
    )

    order.order_status = OrderStatus.COMPLETED
    await session.commit()
    return order
