
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import StockMovementType

class StockItem(Base):
    

    __tablename__ = "stock_item"

    id: Mapped[int] = mapped_column(
        "stock_item_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    product_id: Mapped[int] = mapped_column(
        "product_id",
        BigInteger,
        ForeignKey("product.product_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shelf_id: Mapped[int] = mapped_column(
        "shelf_id",
        BigInteger,
        ForeignKey("shelf.shelf_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey("warehouse.warehouse_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        "quantity",
        Numeric(12, 3),
        nullable=False,
    )
    package_type: Mapped[str] = mapped_column(
        "package_type",
        String(30),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product = relationship("Product", lazy="selectin")
    shelf = relationship("Shelf", lazy="selectin")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_stock_item_quantity_positive"),
        UniqueConstraint(
            "shelf_id",
            "product_id",
            "package_type",
            name="uq_stock_item_shelf_product_package",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"StockItem(id={self.id!r}, product_id={self.product_id!r}, "
            f"shelf_id={self.shelf_id!r}, quantity={self.quantity!r})"
        )

class StockMovement(Base):
    

    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(
        "stock_movement_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    product_id: Mapped[int] = mapped_column(
        "product_id",
        BigInteger,
        ForeignKey("product.product_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shelf_id: Mapped[int] = mapped_column(
        "shelf_id",
        BigInteger,
        ForeignKey("shelf.shelf_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey("warehouse.warehouse_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        "quantity",
        Numeric(12, 3),
        nullable=False,
    )
    movement_type: Mapped[StockMovementType] = mapped_column(
        "movement_type",
        Enum(StockMovementType, name="stock_movement_type", native_enum=False),
        nullable=False,
    )
    order_id: Mapped[int | None] = mapped_column(
        "order_id",
        BigInteger,
        nullable=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        "created_by_user_id",
        BigInteger,
        ForeignKey("user.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product = relationship("Product", lazy="selectin")

    __table_args__ = (
        CheckConstraint("quantity <> 0", name="check_stock_movement_quantity_not_zero"),
    )

    def __repr__(self) -> str:
        return (
            f"StockMovement(id={self.id!r}, product_id={self.product_id!r}, "
            f"quantity={self.quantity!r}, type={self.movement_type!r})"
        )


class LpnContainer(Base):
    __tablename__ = "lpn_containter"
    
    id: Mapped[int] = mapped_column(
        "lpn_containter_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    
    qr: Mapped[str] = mapped_column(String(255), nullable=False)
    
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouse.warehouse_id", ondelete="CASCADE"),
        nullable=False,
        index = True,
    )
    
    shelf_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shelf.shelf_id", ondelete = "SET NULL"),
        nullable=True,
        index = True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False,
        server_default=func.now()
    )
    
    __table_args__ = (UniqueConstraint("qr", name = "unique_lpn_container_qr"),)