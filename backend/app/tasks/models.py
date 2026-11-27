from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    text,
    DateTime,
    Index,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates
)

from app.core.enums import (
    TaskType,
    TaskStatus,
    TaskStepStatus,
)
from app.core.db import Base

from app.products.models import Product
from app.orders.models import InboundOrder
from app.users.models import User


class WarehouseTask(Base):
    __tablename__ = "warehouse_task"
    
    id: Mapped[int] = mapped_column(
        "warehouse_task_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    inbound_order_id: Mapped[int] = mapped_column(
        "inbound_order_id",
        BigInteger,
        ForeignKey(
            "inbound_order.inbound_order_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    task_type: Mapped[TaskType] = mapped_column(
        "task_type",
        Enum(
            TaskType,
            name="task_type",
            native_enum=False,
        ),
        nullable=False,
        default=TaskType.PUTAWAY,
    )
    task_status: Mapped[TaskStatus] = mapped_column(
        "task_status",
        Enum(
            TaskStatus,
            name="task_status",
            native_enum=False,
        ),
        nullable=False,
        default=TaskStatus.NEW,
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        "priority",
        Integer,
        nullable=False,
        default=1,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        "created_by_user_id",
        BigInteger,
        ForeignKey(
            "user.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        "notes",
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        "started_at",
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        "completed_at",
        DateTime(timezone=True),
        nullable=True,
    )
    
    inbound_order: Mapped["InboundOrder"] = relationship(
        "InboundOrder",
        lazy="selectin"
    )
    created_by_user: Mapped["User"] = relationship(
        "User",
        foreign_key=[created_by_user_id],
        lazy="selectin",
    )
    assignees: Mapped[list["WarehouseTaskAssignee"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    steps: Mapped[list["WarehouseTaskStep"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WarehouseTaskStep.id",
    )
    
    __table_args__ = (
        CheckConstraint(
            "priority BETWEEN 1 AND 100",
            name="check_warehouse_task_priority_range",
        ),
        # Захист від дублів на рівні БД (+ захист від race condition).
        # Дозволяє перестворити завдання лише якщо попереднє було скасовано.
        Index(
            "unique_active_putaway_task_per_inbound_order",
            "inbound_order_id",
            unique=True,
            postgresql_where=text("task_status != 'canceled'"),
        ),
    )
    
    @validates("priority")
    def validate_priority(self, key: str, value: int) -> int:
        is_valid_priority: bool = (
            value is not None
            and 1 <= int(value) <= 100
        )
        if not is_valid_priority:
            raise ValueError(
                f"Attribute {key!r} must be between 1 and 100 (received {value!r})"
            )
        
        return int(value)
    
    def __repr__(self) -> str:
        return (
            f"WarehouseTask(id={self.id!r}, "
            f"inbound_order_id={self.inbound_order_id!r}, "
            f"status={self.task_status.value!r})"
        )


class WarehouseTaskAssignee(Base):
    __tablename__ = 'warehouse_task_assignees'
    
    id: Mapped[int] = mapped_column(
        "warehouse_task_assignee_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    warehouse_task_id: Mapped[int] = mapped_column(
        "warehouse_task_id",
        BigInteger,
        ForeignKey(
            "warehouse_task.warehouse_task_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        "user_id",
        BigInteger,
        ForeignKey(
            "user.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        "assigned_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    task: Mapped["WarehouseTask"] = relationship(
        "WarehouseTask",
        back_populates="assignees",
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_key=[user_id],
        lazy="selectin",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "warehouse_task_id", "user_id",
            name="unique_warehouse_task_assignee_task_user",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"WarehouseTaskAssignee(id={self.id!r}, "
            f"task_id={self.warehouse_task_id!r}, "
            f"user_id={self.user_id!r})"
        )


class WarehouseTaskStep(Base):
    __tablename__ = "warehouse_task_step"
    
    id: Mapped[int] = mapped_column(
        "warehouse_task_step_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    warehouse_task_id: Mapped[int] = mapped_column(
        "warehouser_task_id",
        BigInteger,
        ForeignKey(
            "warehouse_task.warehouse_task_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    inbound_order_item_id: Mapped[int] = mapped_column(
        "inbound_order_item_id",
        BigInteger,
        ForeignKey(
            "inbound_order_item.inbound_order_item_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        "product_id",
        BigInteger,
        ForeignKey(
            "product.product_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    target_shelf_id: Mapped[int | None] = mapped_column(
        "target_shelf_id",
        BigInteger,
        ForeignKey(
            "shelf.shelf_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    completed_by_user_id: Mapped[int | None] = mapped_column(
        "completed_by_user_id",
        BigInteger,
        ForeignKey(
            "user.user_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    planned_quantity: Mapped[Decimal] = mapped_column(
        "planned_quantity",
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    actual_quantity: Mapped[Decimal] = mapped_column(
        "actual_quantity",
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    package_type: Mapped[str] = mapped_column(
        "package_type",
        String(30),
        nullable=False,
    )
    step_status: Mapped[TaskStepStatus] = mapped_column(
        "step_status",
        Enum(
            TaskStepStatus,
            name="task_step_status",
            native_enum=False,
        ),
        nullable=False,
        default=TaskStepStatus.PENDING,
    )
    
    task: Mapped["WarehouseTask"] = relationship(
        "WarehouseTask",
        back_populates="steps",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        lazy="selectin",
    )
    completed_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[completed_by_user_id],
        lazy="selectin",
    )
    
    __table_args__ = (
        CheckConstraint(
            "planned_quantity > 0",
            name="check_warehouse_task_step_planned_quantity_positive",
        ),
        CheckConstraint(
            "actual_quantity >= 0",
            name="check_warehouse_task_step_actual_quantity_non_negative",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"WarehouseTaskStep(id={self.id!r}, "
            f"task_id={self.warehouse_task_id!r}, "
            f"product_id={self.product_id!r})"
        )
