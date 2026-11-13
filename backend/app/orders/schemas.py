from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from app.core.enums import OrderStatus

# Inbound order item

class InboundOrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(
        ...,
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=2,
    )
    # TODO: str VS package_type table (id, name)
    package_type: str = Field(..., max_length=30)

class InboundOrderItemResponse(BaseModel):
    item_id: int
    product_id: int
    quantity: Decimal
    # TODO: str VS package_type table (id, name)
    package_type: str = Field(..., max_length=30)
    
    # Allows Pydantic to read data directly from SQLAlchemy (ORM) models
    model_config = ConfigDict(from_attributes=True)

# Inbound order

class InboundOrderCreate(BaseModel):
    supplier_id: int
    invoice_number: str = Field(..., max_length=50)
    expected_delivery_date: datetime
    order_status: OrderStatus = OrderStatus.DRAFT
    items: list[InboundOrderItemCreate] = Field(..., min_length=1)

class InboundOrderUpdate(BaseModel):
    supplier_id: int | None = None
    invoice_number: str | None = Field(default=None, max_length=50)
    expected_delivery_date: datetime | None = None
    order_status: OrderStatus | None = None
    items: list[InboundOrderItemCreate] | None = None

class InboundOrderResponse(BaseModel):
    inbound_order_id: int
    supplier_id: int
    invoice_number: str
    expected_delivery_date: datetime
    order_status: OrderStatus
    created_by_user_id: int
    created_at: datetime
    items: list[InboundOrderItemResponse]
    
    # Allows Pydantic to read data directly from SQLAlchemy (ORM) models
    model_config = ConfigDict(from_attributes=True)