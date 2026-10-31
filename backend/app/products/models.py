from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    CheckConstraint,
    func,
    DateTime
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates
)

from app.core.enums import UnitOfMeasure, SupplierStatus
from app.core.db import Base
from app.core.validators import validate_positive_decimal, validate_non_negative_decimal

class Category(Base):
    __tablename__ = 'category'
    
    id: Mapped[int] = mapped_column(
        "category_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        "category_name",
        String(150),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        "category_description",
        Text,
        nullable=True
    )
    
    products: Mapped[list["Product"]] = relationship(back_populates="category")
    
    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, name={self.name!r})"

class Product(Base):
    __tablename__ = 'product'
    
    id: Mapped[int] = mapped_column(
        "product_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    sku_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        "product_name",
        String(255),
        nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "category.category_id",
            ondelete="RESTRICT",
        ),
        nullable=False
    )
    unit_of_measure: Mapped[UnitOfMeasure] = mapped_column(
        Enum(
            UnitOfMeasure,
            name="unit_of_measure",
            native_enum=False
        ),
        nullable=False
    )
    width: Mapped[Decimal] = mapped_column(
        "product_width",
        Numeric(8, 2),
        nullable=False
    )
    length: Mapped[Decimal] = mapped_column(
        "product_length",
        Numeric(8, 2),
        nullable=False
    )
    height: Mapped[Decimal] = mapped_column(
        "product_height",
        Numeric(8, 2),
        nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(
        "product_weight",
        Numeric(10, 3),
        nullable=False
    )
    min_stock_level: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True
    )
    
    category: Mapped["Category"] = relationship(back_populates="products")
    
    __table_args__ = (
        CheckConstraint(
            "product_length > 0",
            name="check_product_length_min",
        ),
        CheckConstraint(
            "product_width > 0",
            name="check_product_width_min",
        ),
        CheckConstraint(
            "product_height > 0",
            name="check_product_height_min",
        ),
        CheckConstraint(
            "product_weight > 0",
            name="check_product_weight_min",
        ),
        CheckConstraint(
            "min_stock_level IS NULL OR min_stock_level >= 0",
            name="check_product_min_stock_level",
        ),
    )
    
    @validates("width")
    def validate_product_width(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("length")
    def validate_product_length(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("height")
    def validate_product_height(self, key, value):
        return validate_positive_decimal(key, value)

    @validates("weight")
    def validate_product_weight(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("min_stock_level")
    def validate_min_stock_level(self, key, value):
        return validate_non_negative_decimal(key, value)
    
    def __repr__(self) -> str:
        return f"Product(id={self.id!r}, name={self.name!r}, SKU={self.sku_code!r})"
    
class Supplier(Base):
    __tablename__ = 'supplier'
    
    id: Mapped[int] = mapped_column(
        "supplier_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True
    )
    contact_person: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )
    phone_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        "supplier_email",
        String(100),
        nullable=True
    )
    address: Mapped[str | None] = mapped_column(
        "supplier_address",
        Text,
        nullable=True
    )
    status: Mapped[SupplierStatus] = mapped_column(
        "supplier_status",
        Enum(
            SupplierStatus,
            name="supplier_status",
            native_enum=False
        ),
        nullable=False,
        default=SupplierStatus.ACTIVE,
        server_default=SupplierStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        "supplier_created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )