from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    String,
    Enum,
    func,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import OrderStatus

class InboundOrder(Base):
    __tablename__ = "inbound_order"
    
    id: Mapped[int] = mapped_column(
        "inbound_order_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    supplier_id: Mapped[int] = mapped_column(
        "supplier_id",
        BigInteger,
        ForeignKey(
            "supplier.supplier_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(
        "invoice_number",
        String(50),
        nullable=False,
    )
    expected_delivery_date: Mapped[datetime] = mapped_column(
        "expected_delivery_date",
        DateTime(timezone=True),
        nullable=False,
    )
    order_status: Mapped[OrderStatus] = mapped_column(
        "order_status",
        Enum(
            OrderStatus,
            name="order_status",
            native_enum=False,
        ),
        nullable=False,
        default=OrderStatus.DRAFT,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        "created_by_user_id",
        BigInteger,
        ForeignKey(
            "user.user_id",
            ondelete="RESTRICT"
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    supplier = relationship(
        "Supplier",
        lazy="selectin",
    )
    created_by_user = relationship(
        "User",
        lazy="selectin",
    )
    items: Mapped[list["InboundOrderItem"]] = relationship(
        back_populates="inbound_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "invoice_number",
            name="unique_supplier_invoice_number",
        ),
    )
    
    def __repr__(self) -> str:
        return f"InboundOrder(id={self.id!r}, invoice_number={self.invoice_number!r})"

class InboundOrderItem(Base):
    __tablename__ = "inbound_order_item"
    
    id: Mapped[int] = mapped_column(
        "inbound_order_item_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    inbound_order_id: Mapped[int] = mapped_column(
        "inbound_order_id",
        BigInteger,
        ForeignKey(
            "inbound_order.inbound_order_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        "product_id",
        BigInteger,
        ForeignKey(
            "product.product_id",
            ondelete="RESTRICT"
        ),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        "quantity",
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    package_type: Mapped[str] = mapped_column(
        "package_type",
        String(30),
        nullable=False,
    )
    
    inbound_order: Mapped["InboundOrder"] = relationship(
        "InboundOrder",
        back_populates="items",
    )
    product = relationship(
        "Product",
        lazy="selectin",
    )
    
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="check_inbound_order_item_quantity_positive",
        ),
        # TODO:
        #  -product_id?
        #  -package_type?
        #  +batch_number?
        UniqueConstraint(
            "inbound_order_id",
            "product_id",
            "package_type",
            name="unique_order_product_package",
        )
    )
    
    def __repr__(self) -> str:
        return f"InboundOrderItem(id={self.id!r}, inbound_order_id={self.inbound_order_id!r})"