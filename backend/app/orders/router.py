
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import OrderStatus, OrderType, RoleName
from app.core.rbac import ADMIN_ROLES, ALL_ROLES
from app.core.units import volume_m3
from app.routers.map import _check_warehouse_access
from app.utils.role_checker import RoleChecker
from app.orders import crud, outbound_crud
from app.orders import list_service
from app.orders import posting
from app.orders.models import InboundOrder, OutboundOrder
from app.orders.schemas import (
    CapacityCheckResponse,
    InboundOrderCreate,
    InboundOrderResponse,
    InboundOrderUpdate,
    InboundOrderItemResponse,
    OrderListItem,
    OrderListResponse,
    OutboundOrderCreate,
    OutboundOrderResponse,
    OutboundOrderUpdate,
    OutboundOrderItemResponse,
    PostOrderResult,
    StockLevelResponse,
)
from app.products.models import Product
from app.stock import service as stock_service
from app.stock.models import StockItem
from app.warehouses.services import fill_service

router: APIRouter = APIRouter(
    prefix="/api/v1/inbound-orders",
    tags=["Inbound Orders"],
)

outbound_router: APIRouter = APIRouter(
    prefix="/api/v1/outbound-orders",
    tags=["Outbound Orders"],
)

orders_router: APIRouter = APIRouter(
    prefix="/api/v1/orders",
    tags=["Orders"],
)

stock_router: APIRouter = APIRouter(
    prefix="/api/v1/stock",
    tags=["Stock"],
)

require_manager_or_admin: RoleChecker = RoleChecker(
    RoleName.ROOT.value,
    RoleName.ADMIN.value,
    RoleName.WAREHOUSE_MANAGER.value,
)
require_authenticated: RoleChecker = RoleChecker(
    *[role.value for role in ALL_ROLES]
)

def _scoped_warehouse(current_user: dict, warehouse_id: int | None) -> int | None:
    """Фільтр складу для списків: менеджер і комірник бачать лише накладні свого складу."""
    if current_user.get("role") in ADMIN_ROLES:
        return warehouse_id
    own = current_user.get("warehouse_id")
    if own is None or (warehouse_id is not None and warehouse_id != own):
        # Та сама відповідь, що й у _check_warehouse_access
        _check_warehouse_access(current_user, warehouse_id if warehouse_id is not None else -1)
    return own

def _ensure_editable(order: InboundOrder | OutboundOrder) -> None:
    """Проведена накладна вже змінила залишки: правка зробила б їх неузгодженими,
    а повернення в чернетку дозволило б провести її вдруге (подвійний рух товару)."""
    if order.order_status == OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Накладну {order.invoice_number} проведено - змінювати її не можна",
        )

def _to_response(
    order: InboundOrder
) -> InboundOrderResponse:
    return InboundOrderResponse(
        inbound_order_id=order.id,
        supplier_id=order.supplier_id,
        warehouse_id=order.warehouse_id,
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

def _outbound_to_response(
    order: OutboundOrder
) -> OutboundOrderResponse:
    return OutboundOrderResponse(
        outbound_order_id=order.id,
        recipient_id=order.recipient_id,
        warehouse_id=order.warehouse_id,
        invoice_number=order.invoice_number,
        planned_shipment_date=order.planned_shipment_date,
        order_status=order.order_status,
        created_by_user_id=order.created_by_user_id,
        created_at=order.created_at,
        items=[
            OutboundOrderItemResponse(
                item_id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                package_type=item.package_type,
            ) for item in order.items
        ],
    )

def _shortage_error(status_code: int, message: str, shortages: list[dict]) -> HTTPException:
    
    return HTTPException(
        status_code=status_code,
        detail={"message": message, "shortages": shortages},
    )

@router.get(
    "/{order_id}",
    response_model=InboundOrderResponse,
    summary="Get Inbound Order by ID",
)
async def get_inbound_order(
    order_id: int,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> InboundOrderResponse:
    order: InboundOrder = await crud.get_inbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)
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
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[InboundOrderResponse]:
    orders, _ = await crud.list_inbound_orders(
        session,
        search=search,
        order_status=order_status,
        supplier_id=supplier_id,
        warehouse_id=_scoped_warehouse(current_user, warehouse_id),
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
    _check_warehouse_access(current_user, data.warehouse_id)
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
        crud.WarehouseNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except crud.SupplierNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    current_user: dict = Depends(require_manager_or_admin),
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
    _check_warehouse_access(current_user, order.warehouse_id)
    if data.warehouse_id is not None:
        _check_warehouse_access(current_user, data.warehouse_id)
    _ensure_editable(order)

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
        crud.WarehouseNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except crud.SupplierNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    current_user: dict = Depends(require_manager_or_admin),
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
    _check_warehouse_access(current_user, order.warehouse_id)

    try:
        await crud.delete_inbound_order(session, order)
    except crud.InboundOrderCannotBeDeletedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post(
    "/{order_id}/post",
    response_model=PostOrderResult,
    summary="Провести прихідну накладну",
    description=(
        "Приймає товар на склад: розміщує партії на полицях із вільним місцем "
        "і переводить накладну у статус «Завершено». "
        "Якщо місця не вистачає - 409 із переліком товарів, які не вдалося розмістити."
    ),
)
async def post_inbound_order(
    order_id: int,
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> PostOrderResult:
    order: InboundOrder = await crud.get_inbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)

    try:
        posted = await posting.post_inbound_order(
            session, order, current_user.get("id", 1)
        )
    except posting.OrderCannotBePostedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except stock_service.InsufficientCapacityError as e:
        raise _shortage_error(
            status.HTTP_409_CONFLICT,
            "Недостатньо місця на полицях складу - накладну не проведено",
            [shortage.to_dict() for shortage in e.shortages],
        ) from e

    total = sum((Decimal(str(item.quantity)) for item in posted.items), Decimal("0"))
    return PostOrderResult(
        order_id=posted.id,
        order_type=OrderType.INBOUND,
        order_status=posted.order_status,
        posted_at=posted.created_at,
        items_count=len(posted.items),
        total_quantity=str(total),
        processed_quantity=str(total),
    )

@router.post(
    "/capacity-check",
    response_model=CapacityCheckResponse,
    summary="Перевірити вміщуваність партії на полицях складу",
)
async def check_inbound_capacity(
    items: list[dict],
    warehouse_id: int = Query(..., description="Склад, на якому перевіряємо місце"),
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> CapacityCheckResponse:
    _check_warehouse_access(current_user, warehouse_id)

    parsed: list[tuple[int, Decimal, str]] = []
    for raw in items:
        try:
            product_id = int(raw.get("product_id"))
            quantity = Decimal(str(raw.get("quantity", "0")))
            package_type = str(raw.get("package_type", "box"))
        except (TypeError, ValueError, ArithmeticError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Некоректний формат позиції",
            ) from None
        if product_id <= 0 or quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Кількість має бути > 0",
            )
        parsed.append((product_id, quantity, package_type))

    capacity = await fill_service.get_warehouse_capacity(session, warehouse_id)
    products = await stock_service.get_products(
        session, [item[0] for item in parsed]
    )

    required_volume = Decimal("0")
    required_weight = Decimal("0")
    for product_id, quantity, _package_type in parsed:
        product = products.get(product_id)
        if product is None:
            continue
        required_volume += volume_m3(
            product.width, product.length, product.height
        ) * quantity
        required_weight += Decimal(str(product.weight)) * quantity

    shortages = await stock_service.place_incoming(
        session, warehouse_id, parsed, order_id=None
    )
    await session.rollback()

    free_volume = Decimal(str(capacity["free_volume_m3"]))
    free_weight = Decimal(str(capacity["free_weight_kg"]))

    return CapacityCheckResponse(
        fits=not shortages,
        required_m3=round(float(required_volume), 4),
        free_m3=round(float(free_volume), 4),
        total_m3=round(float(capacity["total_volume_m3"]), 4),
        required_weight_kg=round(float(required_weight), 3),
        free_weight_kg=round(float(free_weight), 3),
        shortages=[
            {
                "product_id": s.product_id,
                "product_name": s.product_name,
                "sku_code": s.sku_code,
                "requested": str(s.requested),
                "placed": str(s.placed),
                "unplaced": str(s.unplaced),
                "reason": s.reason,
            }
            for s in shortages
        ],
    )

@outbound_router.get(
    "",
    response_model=list[OutboundOrderResponse],
    summary="Список вихідних накладних",
)
async def list_outbound_orders(
    search: str | None = None,
    order_status: OrderStatus | None = None,
    recipient_id: int | None = None,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[OutboundOrderResponse]:
    orders, _ = await outbound_crud.list_outbound_orders(
        session,
        search=search,
        order_status=order_status,
        recipient_id=recipient_id,
        warehouse_id=_scoped_warehouse(current_user, warehouse_id),
        page=page,
        page_size=page_size,
    )
    return [_outbound_to_response(order) for order in orders]

@outbound_router.get(
    "/{order_id}",
    response_model=OutboundOrderResponse,
    summary="Отримати вихідну накладну за id",
)
async def get_outbound_order(
    order_id: int,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> OutboundOrderResponse:
    order = await outbound_crud.get_outbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)
    return _outbound_to_response(order)

@outbound_router.post(
    "",
    response_model=OutboundOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити вихідну накладну",
    description=(
        "Створює накладну як чернетку. Номер присвоює бекенд. "
        "Нестача залишків не блокує створення чернетки - вона перевіряється при проведенні."
    ),
)
async def create_outbound_order(
    data: OutboundOrderCreate,
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> OutboundOrderResponse:
    _check_warehouse_access(current_user, data.warehouse_id)
    try:
        order = await outbound_crud.create_outbound_order(
            session,
            data,
            created_by_user_id=current_user.get("id", 1),
        )
    except (
        outbound_crud.RecipientNotFoundError,
        outbound_crud.ProductNotFoundError,
        outbound_crud.WarehouseNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except outbound_crud.RecipientNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e
    except outbound_crud.InvoiceNumberAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return _outbound_to_response(order)

@outbound_router.patch(
    "/{order_id}",
    response_model=OutboundOrderResponse,
    summary="Оновити вихідну накладну",
)
async def update_outbound_order(
    order_id: int,
    data: OutboundOrderUpdate,
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> OutboundOrderResponse:
    order = await outbound_crud.get_outbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)
    if data.warehouse_id is not None:
        _check_warehouse_access(current_user, data.warehouse_id)
    _ensure_editable(order)

    if data.model_dump(exclude_unset=True) == {}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided for the update",
        )

    try:
        updated = await outbound_crud.update_outbound_order(session, order, data)
    except (
        outbound_crud.RecipientNotFoundError,
        outbound_crud.ProductNotFoundError,
        outbound_crud.WarehouseNotFoundError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except outbound_crud.RecipientNotActiveError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e
    except outbound_crud.InvoiceNumberAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except outbound_crud.OutboundOrderCannotBeEditedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return _outbound_to_response(updated)

@outbound_router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити вихідну накладну",
)
async def delete_outbound_order(
    order_id: int,
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    order = await outbound_crud.get_outbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)

    try:
        await outbound_crud.delete_outbound_order(session, order)
    except outbound_crud.OutboundOrderCannotBeDeletedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

@outbound_router.post(
    "/{order_id}/post",
    response_model=PostOrderResult,
    summary="Провести вихідну накладну",
    description=(
        "Списує товар із полиць і переводить накладну у статус «Завершено». "
        "Якщо залишків недостатньо - 409 із переліком товарів і розривом залишку."
    ),
)
async def post_outbound_order(
    order_id: int,
    current_user: dict = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_async_session),
) -> PostOrderResult:
    order = await outbound_crud.get_outbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)

    try:
        posted = await posting.post_outbound_order(
            session, order, current_user.get("id", 1)
        )
    except posting.OrderCannotBePostedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except stock_service.InsufficientStockError as e:
        raise _shortage_error(
            status.HTTP_409_CONFLICT,
            "Недостатньо залишків на складі - накладну не проведено",
            [shortage.to_dict() for shortage in e.shortages],
        ) from e

    total = sum((Decimal(str(item.quantity)) for item in posted.items), Decimal("0"))
    return PostOrderResult(
        order_id=posted.id,
        order_type=OrderType.OUTBOUND,
        order_status=posted.order_status,
        posted_at=posted.created_at,
        items_count=len(posted.items),
        total_quantity=str(total),
        processed_quantity=str(total),
    )

@outbound_router.get(
    "/{order_id}/availability",
    summary="Перевірити достатність залишків для накладної",
)
async def check_outbound_availability(
    order_id: int,
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> dict:

    order = await outbound_crud.get_outbound_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Outbound Order {order_id} not found",
        )
    _check_warehouse_access(current_user, order.warehouse_id)

    items = [
        (item.product_id, Decimal(str(item.quantity)), item.package_type)
        for item in order.items
    ]
    shortages = await stock_service.check_availability(
        session, order.warehouse_id, items
    )
    available = await stock_service.get_available_quantities(
        session, order.warehouse_id, [item[0] for item in items]
    )
    return {
        "fits": not shortages,
        "shortages": [shortage.to_dict() for shortage in shortages],
        "available": {
            str(product_id): str(quantity)
            for product_id, quantity in available.items()
        },
    }

@orders_router.get(
    "",
    response_model=OrderListResponse,
    summary="Список накладних (прихідні й вихідні)",
    description="Фільтри: тип накладної, статус, пошук за номером або контрагентом, дати.",
)
async def list_all_orders(
    order_type: OrderType | None = Query(None, description="inbound або outbound"),
    order_status: OrderStatus | None = None,
    search: str | None = None,
    warehouse_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> OrderListResponse:
    items, total = await list_service.list_orders(
        session,
        order_type=order_type,
        order_status=order_status,
        search=search,
        warehouse_id=_scoped_warehouse(current_user, warehouse_id),
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return OrderListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )

@stock_router.get(
    "",
    response_model=list[StockLevelResponse],
    summary="Залишки товарів на складі",
)
async def get_stock_levels(
    product_ids: str | None = Query(
        None, description="Список id товарів через кому, наприклад 1,2,3"
    ),
    warehouse_id: int | None = Query(None, description="Склад; за замовчуванням - усі"),
    current_user: dict = Depends(require_authenticated),
    session: AsyncSession = Depends(get_async_session),
) -> list[StockLevelResponse]:
    # Менеджер і комірник бачать залишки лише свого складу
    warehouse_id = _scoped_warehouse(current_user, warehouse_id)

    parsed_ids: list[int] | None = None
    if product_ids:
        parsed_ids = []
        for raw in product_ids.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed_ids.append(int(raw))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Некоректний id товару: {raw}",
                ) from None

    totals: dict[int, Decimal] = {}
    if warehouse_id is not None:
        totals = await stock_service.get_available_quantities(
            session, warehouse_id, parsed_ids
        )
    else:
        stmt = select(
            StockItem.product_id,
            func.sum(StockItem.quantity),
        ).group_by(StockItem.product_id)
        if parsed_ids is not None:
            if not parsed_ids:
                return []
            stmt = stmt.where(StockItem.product_id.in_(parsed_ids))
        for product_id, quantity in (await session.execute(stmt)).all():
            totals[product_id] = Decimal(str(quantity))

    if parsed_ids is not None:
        for product_id in parsed_ids:
            totals.setdefault(product_id, Decimal("0"))

    if not totals:
        return []

    products = {
        product.id: product
        for product in (
            await session.scalars(
                select(Product).where(Product.id.in_(list(totals.keys())))
            )
        ).all()
    }

    return [
        StockLevelResponse(
            product_id=product_id,
            product_name=products[product_id].name if product_id in products else "",
            sku_code=products[product_id].sku_code if product_id in products else "",
            unit_of_measure=(
                products[product_id].unit_of_measure.value
                if product_id in products
                else ""
            ),
            available=str(quantity),
            reserved="0",
        )
        for product_id, quantity in sorted(totals.items())
    ]
