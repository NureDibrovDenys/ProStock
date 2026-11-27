from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import RoleName
from app.orders import crud as orders_crud
from app.orders.models import InboundOrder
from app.routers.map import _check_warehouse_access
from app.tasks import crud as task_service
from app.tasks.models import WarehouseTask
from app.tasks.schemas import (
    PutawayTaskCreate,
    WarehouseTaskResponse,
    WarehouseTaskStepResponse, WarehouseTaskAssigneeResponse,
)
from app.utils.role_checker import RoleChecker

tasks_router: APIRouter = APIRouter(
    prefix="/api/v1/inbound-orders",
    tags=["Inbound Orders", "Warehouse Tasks"],
)

require_manager_or_admin: RoleChecker = RoleChecker(
    RoleName.ROOT.value,
    RoleName.ADMIN.value,
    RoleName.WAREHOUSE_MANAGER.value,
)


def _extract_user_id(current_user: dict) -> int:
    """
    Safely extracts the user ID from the auth token without an unsafe fallback.
    """
    user_id = current_user.get("id")
    is_invalid_user_id: bool = (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id <= 0
    )
    if is_invalid_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier in authorization token",
        )
    return user_id


def _task_to_response(task: WarehouseTask) -> WarehouseTaskResponse:
    return WarehouseTaskResponse(
        task_id=task.id,
        warehouse_id=task.warehouse_id,
        inbound_order_id=task.inbound_order_id,
        invoice_number=task.inbound_order.invoice_number,
        task_type=task.task_type,
        task_status=task.task_status,
        priority=task.priority,
        assignees=[
            WarehouseTaskAssigneeResponse(
                user_id=assignee.user_id,
                assigned_at=assignee.assigned_at,
            )
            for assignee in task.assignees
        ],
        created_by_user_id=task.created_by_user_id,
        notes=task.notes,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        steps=[
            WarehouseTaskStepResponse(
                step_id=step.id,
                inbound_order_item_id=step.inbound_order_item_id,
                product_id=step.product_id,
                product_name=step.product.name if step.product else "",
                sku_code=step.product.sku_code if step.product else "",
                target_shelf_id=step.target_shelf_id,
                completed_by_user_id=step.completed_by_user_id,
                planned_quantity=step.planned_quantity,
                actual_quantity=step.actual_quantity,
                package_type=step.package_type,
                step_status=step.step_status,
            )
            for step in task.steps
        ],
    )


@tasks_router.post(
    "/{order_id}/tasks",
    response_model=WarehouseTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a storekeeper task from a confirmed inbound order",
    description=(
        "Creates a put-away task based on a confirmed inbound order. "
        "Protected against duplicate task creation."
    ),
)
async def create_task_from_inbound_order(
    order_id: int = Path(
        ..., gt=0, description="Inbound order ID"
    ),
    data: PutawayTaskCreate = Body(default_factory=PutawayTaskCreate),
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> WarehouseTaskResponse:
    user_id: int = _extract_user_id(current_user)

    inbound_order: InboundOrder = (
        await orders_crud.get_inbound_order(session, order_id)
    )
    is_order_missing: bool = inbound_order is None
    if is_order_missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbound order with ID {order_id} was not found",
        )

    _check_warehouse_access(current_user, inbound_order.warehouse_id)

    try:
        created_task: WarehouseTask = await task_service.create_putaway_task_from_inbound_order(
            session=session,
            inbound_order_id=order_id,
            data=data,
            created_by_user_id=user_id,
        )
    except task_service.InboundOrderNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except (
        task_service.InboundOrderNotConfirmedError,
        task_service.TaskAlreadyExistsError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (
        task_service.EmptyInboundOrderError,
        task_service.InvalidAssigneeError,
        task_service.InvalidStepOverrideError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e

    return _task_to_response(created_task)
