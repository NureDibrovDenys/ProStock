from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from app.core.enums import OrderStatus, OrderType

class InboundOrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(
        ...,
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=2,
    )
    package_type: str = Field(..., max_length=30)

class InboundOrderItemResponse(BaseModel):
    item_id: int
    product_id: int
    quantity: Decimal
    package_type: str = Field(..., max_length=30)
    
    model_config = ConfigDict(from_attributes=True)

class InboundOrderCreate(BaseModel):
    supplier_id: int
    warehouse_id: int
    invoice_number: str = Field(..., max_length=50)
    expected_delivery_date: datetime
    order_status: OrderStatus = OrderStatus.DRAFT
    items: list[InboundOrderItemCreate] = Field(..., min_length=1)

class InboundOrderUpdate(BaseModel):
    supplier_id: int | None = None
    warehouse_id: int | None = None
    invoice_number: str | None = Field(default=None, max_length=50)
    expected_delivery_date: datetime | None = None
    order_status: OrderStatus | None = None
    items: list[InboundOrderItemCreate] | None = None

class InboundOrderResponse(BaseModel):
    inbound_order_id: int
    supplier_id: int
    warehouse_id: int
    invoice_number: str
    expected_delivery_date: datetime
    order_status: OrderStatus
    created_by_user_id: int
    created_at: datetime
    items: list[InboundOrderItemResponse]
    
    model_config = ConfigDict(from_attributes=True)

class OutboundOrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(
        ...,
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=2,
    )
    package_type: str = Field(..., max_length=30)

class OutboundOrderItemResponse(BaseModel):
    item_id: int
    product_id: int
    quantity: Decimal
    package_type: str = Field(..., max_length=30)

    model_config = ConfigDict(from_attributes=True)

class OutboundOrderCreate(BaseModel):
    recipient_id: int
    warehouse_id: int
    planned_shipment_date: datetime
    invoice_number: str | None = Field(
        default=None,
        max_length=50,
        description="Необовʼязковий: якщо не заданий, бекенд присвоїть номер накладної",
    )
    order_status: OrderStatus = OrderStatus.DRAFT
    items: list[OutboundOrderItemCreate] = Field(..., min_length=1)

class OutboundOrderUpdate(BaseModel):
    recipient_id: int | None = None
    warehouse_id: int | None = None
    planned_shipment_date: datetime | None = None
    invoice_number: str | None = Field(default=None, max_length=50)
    order_status: OrderStatus | None = None
    items: list[OutboundOrderItemCreate] | None = Field(default=None, min_length=1)

class OutboundOrderResponse(BaseModel):
    outbound_order_id: int
    recipient_id: int
    warehouse_id: int
    invoice_number: str
    planned_shipment_date: datetime
    order_status: OrderStatus
    created_by_user_id: int
    created_at: datetime
    items: list[OutboundOrderItemResponse]

    model_config = ConfigDict(from_attributes=True)

class ShortageItem(BaseModel):
    

    product_id: int
    product_name: str
    sku_code: str
    requested: str
    available: str
    shortage: str

class CapacityShortageItem(BaseModel):
    

    product_id: int
    product_name: str
    sku_code: str
    requested: str
    placed: str
    unplaced: str
    reason: str

class PostOrderResult(BaseModel):
    

    order_id: int
    order_type: OrderType
    order_status: OrderStatus
    posted_at: datetime
    items_count: int
    total_quantity: str
    processed_quantity: str

class OrderListItem(BaseModel):
    

    order_type: OrderType
    order_id: int
    number: str
    invoice_number: str
    counterparty_id: int
    counterparty_name: str
    warehouse_id: int
    order_status: OrderStatus
    date: datetime
    items_count: int
    total_quantity: str

class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int
    pages: int

class StockLevelResponse(BaseModel):
    

    product_id: int
    product_name: str
    sku_code: str
    unit_of_measure: str
    available: str
    reserved: str = "0"

class CapacityCheckResponse(BaseModel):
    

    fits: bool
    required_m3: float
    free_m3: float
    total_m3: float
    required_weight_kg: float = 0.0
    free_weight_kg: float = 0.0
    shortages: list[CapacityShortageItem] = []
