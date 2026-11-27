from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal
from logging import Logger

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.enums import (
    ShelfStatus,
    OrderStatus,
    RoleName,
    TaskStatus,
    TaskStepStatus,
    TaskType,
)
from app.orders.crud import InboundOrderNotFoundError
from app.orders.models import InboundOrder, InboundOrderItem
from app.stock.models import StockItem
from app.tasks.models import WarehouseTask, WarehouseTaskStep
from app.tasks.schemas import PutawayTaskCreate
from app.users.models import User
from app.warehouses.models import Rack, Shelf

logger: Logger = logging.getLogger(__name__)


class InboundOrderNotConfirmedError(Exception):
    pass


class EmptyInboundOrderError(Exception):
    pass


class TaskAlreadyExistsError(Exception):
    def __init__(
        self,
        message: str,
        existing_task_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.existing_task_id = existing_task_id


class InvalidAssigneeError(Exception):
    pass


class InvalidStepOverrideError(Exception):
    pass


def _default_task_options() -> list[LoaderOption]:
    return [
        joinedload(
            WarehouseTask.inbound_order,
            innerjoin=True,
        ),
        selectinload(WarehouseTask.steps).selectinload(WarehouseTaskStep.product),
    ]


async def get_warehouse_task(
    session: AsyncSession,
    task_id: int,
    *,
    options: Sequence[LoaderOption] | None = None,
) -> WarehouseTask | None:
    has_no_custom_options: bool = options is None
    if has_no_custom_options:
        options = _default_task_options()

    task_stmt = (
        select(WarehouseTask)
        .where(WarehouseTask.id == task_id)
        .options(*options)
        .execution_options(populate_existing=True)
    )
    warehouse_task: WarehouseTask | None = await session.scalar(task_stmt)
    return warehouse_task


async def _lock_and_load_inbound_order(
    session: AsyncSession,
    inbound_order_id: int,
) -> InboundOrder:
    """
    Locks the inbound order row (FOR UPDATE) to prevent race conditions.

    Uses `of=InboundOrder` to lock exclusively the order row rather than
    adjacent supplier or product tables (prevents deadlocks in Postgres).
    """
    order_stmt = (
        select(InboundOrder)
        .where(InboundOrder.id == inbound_order_id)
        .options(
            selectinload(InboundOrder.items)
            .selectinload(InboundOrderItem.product),
        )
        .with_for_update(of=InboundOrder)
        .execution_options(populate_existing=True)
    )
    inbound_order: InboundOrder | None = await session.scalar(order_stmt)

    is_order_missing: bool = inbound_order is None
    if is_order_missing:
        raise InboundOrderNotFoundError(
            f"Inbound order with ID {inbound_order_id} was not found"
        )
    return inbound_order


def _ensure_order_confirmed(order: InboundOrder) -> None:
    is_not_confirmed: bool = order.order_status != OrderStatus.COMPLETED
    if is_not_confirmed:
        raise InboundOrderNotConfirmedError(
            f"Order {order.invoice_number} has status '{order.order_status.value}'. "
            "Tasks can only be generated from a confirmed order"
        )

    has_no_items: bool = not order.items
    if has_no_items:
        raise EmptyInboundOrderError(
            f"Order {order.invoice_number} contains no line items"
        )


async def _ensure_no_active_task(
    session: AsyncSession,
    inbound_order_id: int,
    invoice_number: str,
) -> None:
    active_task_stmt = (
        select(WarehouseTask.id)
        .where(
            WarehouseTask.inbound_order_id == inbound_order_id,
            WarehouseTask.task_status != TaskStatus.CANCELED,
        )
    )
    existing_task_id: int | None = await session.scalar(active_task_stmt)

    has_active_task: bool = existing_task_id is not None
    if has_active_task:
        raise TaskAlreadyExistsError(
            f"An active task #{existing_task_id} already exists "
            f"for order {invoice_number}",
            existing_task_id=existing_task_id,
        )


async def _validate_assignee(
    session: AsyncSession,
    assigned_to_user_id: int,
    warehouse_id: int,
) -> None:
    """
    Validates that the storekeeper exists, is active, has the right role,
    and belongs to the order's warehouse.
    """
    assignee: User | None = await session.get(User, assigned_to_user_id)

    is_assignee_missing: bool = assignee is None
    if is_assignee_missing:
        raise InvalidAssigneeError(
            f"User with ID {assigned_to_user_id} was not found"
        )

    is_assignee_inactive: bool = not getattr(assignee, "is_active", True)
    if is_assignee_inactive:
        raise InvalidAssigneeError(
            f"User with ID {assigned_to_user_id} is deactivated and cannot perform tasks"
        )

    user_role = getattr(assignee.role, "name", assignee.role)
    is_not_storekeeper: bool = user_role != RoleName.WORKER.value
    if is_not_storekeeper:
        raise InvalidAssigneeError(
            "Put-away tasks can only be assigned to a user with the storekeeper role"
        )

    is_different_warehouse = assignee.warehouse_id != warehouse_id
    if is_different_warehouse:
        raise InvalidAssigneeError(
            "The selected storekeeper is assigned to a different warehouse"
        )


async def _resolve_target_shelves(
    session: AsyncSession,
    order: InboundOrder,
    data: PutawayTaskCreate,
) -> dict[int, int | None]:
    """
    Determines target shelves for all order items without N+1 queries.

    Priority:
    1. Manual manager assignment from `step_overrides` (verifying shelf belongs to the warehouse).
    2. Shelf in this warehouse that already stores this SKU (batch consolidation).
    3. None — if the storekeeper selects the shelf directly upon scanning on-site.
    """
    order_item_ids: set[int] = {item.id for item in order.items}
    manual_map: dict[int, int] = {}

    has_step_overrides: bool = bool(data.step_overrides)
    if has_step_overrides:
        for override in data.step_overrides:
            is_foreign_item = (
                override.inbound_order_item_id not in order_item_ids
            )
            if is_foreign_item:
                raise InvalidStepOverrideError(
                    f"Item ID {override.inbound_order_item_id} "
                    f"does not belong to order {order.invoice_number}"
                )
            manual_map[override.inbound_order_item_id] = override.target_shelf_id

        # Validate all provided shelves in a single SQL query
        requested_shelf_ids: set[int] = set(manual_map.values())
        valid_shelves_stmt = (
            select(Shelf.id)
            .join(Rack, Shelf.rack_id == Rack.id)
            .where(
                Shelf.id.in_(requested_shelf_ids),
                Rack.warehouse_id == order.warehouse_id,
                Shelf.status == ShelfStatus.ACTIVE,
            )
        )
        valid_shelves_result = await session.scalars(valid_shelves_stmt)
        valid_shelf_ids: set = set(valid_shelves_result.all())
        invalid_shelves: set[int] = requested_shelf_ids - valid_shelf_ids

        has_invalid_shelves: bool = bool(invalid_shelves)
        if has_invalid_shelves:
            raise InvalidStepOverrideError(
                f"Shelves {sorted(invalid_shelves)} were not found or "
                f"belong to another warehouse"
            )

    # For items without a manual shelf,
    # find existing storage locations for the same SKUs in this warehouse
    unresolved_product_ids: set[int] = {
        item.product_id
        for item in order.items
        if item.id not in manual_map
    }
    suggested_shelf_by_product: dict[int, int] = {}

    has_unresolved_products: bool = bool(unresolved_product_ids)
    if has_unresolved_products:
        # Select the shelf with the largest stock balance of the corresponding product
        # in this warehouse (1 query)
        stock_shelves_stmt = (
            select(
                StockItem.product_id,
                StockItem.shelf_id,
                func.sum(StockItem.quantity).label("total_quantity"),
            )
            .join(Shelf, StockItem.shelf_id == Shelf.id)
            .join(Rack, Shelf.rack_id == Rack.id)
            .where(
                Rack.warehouse_id == order.warehouse_id,
                Shelf.status == ShelfStatus.ACTIVE,
                StockItem.product_id.in_(unresolved_product_ids),
                StockItem.quantity > 0,
            )
            .group_by(
                StockItem.product_id,
                StockItem.shelf_id
            )
            .order_by(
                StockItem.product_id,
                func.sum(StockItem.quantity).desc()
            )
        )
        stock_shelf_rows = (await session.execute(stock_shelves_stmt)).all()
        for row in stock_shelf_rows:
            # Pick the first shelf (with the highest stock balance) for each product
            is_product_unmapped: bool = (
                row.product_id not in suggested_shelf_by_product
            )
            if is_product_unmapped:
                suggested_shelf_by_product[row.product_id] = row.shelf_id

    resolved_shelves: dict[int, int | None] = {}
    for item in order.items:
        is_manually_assigned: bool = item.id in manual_map
        if is_manually_assigned:
            resolved_shelves[item.id] = manual_map[item.id]
        else:
            resolved_shelves[item.id] = suggested_shelf_by_product.get(item.product_id)

    return resolved_shelves


async def create_putaway_task_from_inbound_order(
    session: AsyncSession,
    inbound_order_id: int,
    data: PutawayTaskCreate,
    created_by_user_id: int,
) -> WarehouseTask:
    """
    Creates a put-away task from a confirmed inbound order.
    """
    # 1. Pessimistically lock the order row
    locked_order: InboundOrder = await _lock_and_load_inbound_order(
        session, inbound_order_id
    )

    # 2. Verify business status and presence of line items
    _ensure_order_confirmed(locked_order)

    # 3. Ensure no active duplicate task exists
    await _ensure_no_active_task(
        session,
        locked_order.id,
        locked_order.invoice_number
    )

    # 4. Validate the storekeeper (if assigned immediately)
    has_assignee: bool = data.assigned_to_user_id is not None
    if has_assignee:
        await _validate_assignee(
            session,
            assigned_to_user_id=data.assigned_to_user_id,
            warehouse_id=locked_order.warehouse_id,
        )

    # 5. Batch-resolve and validate target shelves
    target_shelves_by_item: dict[int, int | None] = (
        await _resolve_target_shelves(session, locked_order, data)
    )

    initial_status = (
        TaskStatus.ASSIGNED if has_assignee else TaskStatus.NEW
    )

    task: WarehouseTask = WarehouseTask(
        warehouse_id=locked_order.warehouse_id,
        inbound_order_id=locked_order.id,
        task_type=TaskType.PUTAWAY,
        task_status=initial_status,
        priority=data.priority,
        assigned_to_user_id=data.assigned_to_user_id,
        created_by_user_id=created_by_user_id,
        notes=data.notes,
    )
    session.add(task)

    try:
        await session.flush()

        steps: list[WarehouseTaskStep] = [
            WarehouseTaskStep(
                warehouse_task_id=task.id,
                inbound_order_item_id=item.id,
                product_id=item.product_id,
                target_shelf_id=target_shelves_by_item.get(item.id),
                planned_quantity=item.quantity,
                actual_quantity=Decimal("0.00"),
                package_type=item.package_type,
                step_status=TaskStepStatus.PENDING,
            )
            for item in locked_order.items
        ]
        session.add_all(steps)

        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        original_error = getattr(e, "orig", None)
        is_unique_violation: bool = bool(
            original_error
            and getattr(original_error, "sqlstate", None) == "23505"
        )
        if is_unique_violation:
            logger.warning(
                "Attempt to create duplicate task for inbound order id=%s by user_id=%s",
                inbound_order_id,
                created_by_user_id,
            )
            raise TaskAlreadyExistsError(
                f"A task has already been created for order {locked_order.invoice_number}"
            ) from e
        raise

    logger.info(
        "Created put-away task task_id=%s for order id=%s (warehouse=%s, created_by=%s)",
        task.id,
        locked_order.id,
        locked_order.warehouse_id,
        created_by_user_id,
    )

    created_task: WarehouseTask | None = await get_warehouse_task(session, task.id)
    return created_task
