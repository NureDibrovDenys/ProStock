"""
REST API for inbound orders.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import OrderStatus, RoleName
from app.core.rbac import ALL_ROLES
from app.utils.role_checker import RoleChecker
from app.orders import crud
from app.orders.schemas import (
    InboundOrderCreate,
    InboundOrderResponse,
    InboundOrderUpdate, InboundOrderItemResponse,
)
from app.orders.models import InboundOrder

router: APIRouter = APIRouter(
    prefix="/api/v1/inbound-orders",
    tags=["Inbound Orders"],
)

require_manager_or_admin: RoleChecker = RoleChecker(
    RoleName.ROOT.value,
    RoleName.ADMIN.value,
    RoleName.WAREHOUSE_MANAGER.value,
)
require_authenticated: RoleChecker = RoleChecker(
    *[role.value for role in ALL_ROLES]
)

def _to_response(
    order: InboundOrder
) -> InboundOrderResponse:
    return InboundOrderResponse(
        inbound_order_id=order.id,
        supplier_id=order.supplier_id,
        invoice_number=order.invoice_number,
        expected_delivery_date=order.expected_delivery_date,
        order_status=order.order_status,
        created_by_user_id=order.created_by_user_id,
        created_at=order.created_at,
        items=[
            InboundOrderItemResponse(
                item_id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                package_type=item.package_type,
            ) for item in order.items
        ],
    )

@router.get(
    "/{order_id}",
    response_model=InboundOrderResponse,
    summary="Get Inbound Order by ID",
)
async def get_inbound_order(
    order_id: int,
    _: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> InboundOrderResponse:
    order: InboundOrder = await crud.get_inbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbound Order {order_id} not found",
        )
    return _to_response(order)

@router.get(
    "",
    response_model=list[InboundOrderResponse],
    summary="Get Inbound Orders",
)
async def list_inbound_orders(
    search: str | None = None,
    order_status: OrderStatus | None = None,
    supplier_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    _: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[InboundOrderResponse]:
    orders, _ = await crud.list_inbound_orders(
        session,
        search=search,
        order_status=order_status,
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )
    return [_to_response(order) for order in orders]

@router.post(
    "",
    response_model=InboundOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Inbound Orders",
)
async def create_inbound_order(
    data: InboundOrderCreate,
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> InboundOrderResponse:
    try:
        user_id = current_user.get("id", 1) # get user ID from token
        order = await crud.create_inbound_order(
            session,
            data,
            created_by_user_id=user_id,
        )
    except (
        crud.SupplierNotFoundError,
        crud.ProductNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except crud.InvoiceNumberAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return _to_response(order)

@router.patch(
    "/{order_id}",
    response_model=InboundOrderResponse,
    summary=f"Update Inbound Order by ID",
)
async def update_inbound_order(
    order_id: int,
    data: InboundOrderUpdate,
    _: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> InboundOrderResponse:
    order: InboundOrder = await crud.get_inbound_order(
        session, order_id
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbound Order {order_id} not found",
        )
    
    if data.model_dump(exclude_unset=True) == {}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided for the update",
        )
    
    try:
        updated_order: InboundOrder = await crud.update_inbound_order(
            session, order, data
        )
    except (
        crud.SupplierNotFoundError,
        crud.ProductNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except crud.InvoiceNumberAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return _to_response(updated_order)

@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary=f"Delete Inbound Order by ID",
)
async def delete_inbound_order(
    order_id: int,
    _: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    order: InboundOrder = await crud.get_inbound_order(
        session, order_id
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbound Order {order_id} not found",
        )
    
    try:
        await crud.delete_inbound_order(session, order)
    except crud.InboundOrderCannotBeDeletedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )