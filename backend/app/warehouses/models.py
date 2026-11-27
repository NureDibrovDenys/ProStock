from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Boolean,
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
    ObstacleType,
    PointType,
    ZoneType,
    ShelfStatus,
    InactiveReason,
    TaskType,
    TaskStatus,
    TaskStepStatus,
)
from app.core.db import Base
from app.core.validators import (
    validate_positive_decimal,
    validate_non_negative_decimal,
    validate_rotation_angle,
)

from app.products.models import Product
from app.orders.models import InboundOrder
from app.users.models import User

class Warehouse(Base):
    __tablename__ = "warehouse"
    
    id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        "warehouse_name",
        String(150),
        nullable=False
    )
    address: Mapped[str | None] = mapped_column(
        "warehouse_address",
        Text,
        nullable=True
    )
    total_area: Mapped[Decimal] = mapped_column(
        "total_warehouse_area",
        Numeric(10, 2),
        nullable=False
    )
    
    grids: Mapped[list["WarehouseGrid"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    walls: Mapped[list["WarehouseWall"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    partitions: Mapped[list["WarehousePartition"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    obstacles: Mapped[list["WarehouseObstacle"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    entry_points: Mapped[list["WarehouseEntryPoint"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    zones: Mapped[list["Zone"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    racks: Mapped[list["Rack"]] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        CheckConstraint(
            "total_warehouse_area > 0",
            name="check_warehouse_total_area_min"
        ),
    )
    
    @validates("total_area")
    def validate_total_warehouse_area(self, key, value):
        return validate_positive_decimal(key, value)
    
    def __repr__(self) -> str:
        return f"Warehouse(id={self.id!r}, name={self.name!r})>"

class WarehouseGrid(Base):
    __tablename__ = 'warehouse_grid'

    id: Mapped[int] = mapped_column(
        "grid_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    cell_size: Mapped[Decimal] = mapped_column(
        "cell_size",
        Numeric(8, 2),
        nullable=False,
        default=Decimal("1.00"),
        server_default=text("1.00")
    )
    grid_width: Mapped[Decimal] = mapped_column(
        "grid_width",
        Numeric(10, 2),
        nullable=False
    )
    grid_height: Mapped[Decimal] = mapped_column(
        "grid_height",
        Numeric(10, 2),
        nullable=False
    )
    
    warehouse: Mapped["Warehouse"] = relationship(back_populates="grids")
    
    __table_args__ = (
        CheckConstraint(
            "cell_size > 0",
            name="check_grid_cell_size_min"
        ),
        CheckConstraint(
            "grid_width > 0",
            name="check_grid_width_min"
        ),
        CheckConstraint(
            "grid_height > 0",
            name="check_grid_height_min"
        ),
    )
    
    @validates("cell_size")
    def validate_cell_size(self, key, value):
        return validate_positive_decimal(key, value)

    @validates("grid_width")
    def validate_grid_width(self, key, value):
        return validate_positive_decimal(key, value)

    @validates("grid_height")
    def validate_grid_height(self, key, value):
        return validate_positive_decimal(key, value)
    
    def __repr__(self) -> str:
        return f"WarehouseGrid(id={self.id!r}, warehouse_id={self.warehouse_id!r})"

class WarehouseWall(Base):
    __tablename__ = 'warehouse_wall'

    id: Mapped[int] = mapped_column(
        "wall_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    vertex_order: Mapped[int] = mapped_column(
        "vertex_order",
        Integer,
        nullable=False
    )
    x: Mapped[Decimal] = mapped_column(
        "coord_x",
        Numeric(8, 2),
        nullable=False
    )
    y: Mapped[Decimal] = mapped_column(
        "coord_y",
        Numeric(8, 2),
        nullable=False
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="walls")
    
    __table_args__ = (
        UniqueConstraint(
            "warehouse_id",
            "vertex_order",
            name="unique_vertex_per_warehouse"
        ),
        CheckConstraint(
            "vertex_order >= 1",
            name="check_wall_vertex_order_min"
        ),
    )
    
    @validates("vertex_order")
    def validate_vertex_order(self, key, value):
        if value is None:
            raise ValueError(f"Атрибут {key!r} не може бути None")
        try:
            integer_value: int = int(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Атрибут {key!r} має бути числом (отримано: {value!r})"
            )
        if integer_value <= 0:
            raise ValueError(
                f"Атрибут {key!r} має бути додатним (отримано: {value!r})"
            )
        return integer_value

    def __repr__(self) -> str:
        return f"WarehouseWall(id={self.id!r}, vertex_order={self.vertex_order!r})"

class WarehousePartition(Base):
    __tablename__ = 'warehouse_partition'

    id: Mapped[int] = mapped_column(
        "partition_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    start_x: Mapped[Decimal] = mapped_column(
        "start_x",
        Numeric(8, 2),
        nullable=False
    )
    start_y: Mapped[Decimal] = mapped_column(
        "start_y",
        Numeric(8, 2),
        nullable=False
    )
    end_x: Mapped[Decimal] = mapped_column(
        "end_x",
        Numeric(8, 2),
        nullable=False
    )
    end_y: Mapped[Decimal] = mapped_column(
        "end_y",
        Numeric(8, 2),
        nullable=False
    )
    thickness: Mapped[Decimal] = mapped_column(
        "thickness",
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.20"),
        server_default=text("0.20")
    )
    height: Mapped[Decimal | None] = mapped_column(
        "height",
        Numeric(8, 2),
        nullable=True
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="partitions")

    __table_args__ = (
        CheckConstraint(
            "thickness > 0",
            name="check_partition_thickness_min"
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="check_partition_height"
        ),
    )

    @validates("thickness")
    def validate_thickness(self, key, value):
        return validate_positive_decimal(key, value)

    @validates("height")
    def validate_height(self, key, value):
        if value is None:
            return None
        return validate_positive_decimal(key, value)

    def __repr__(self) -> str:
        return f"WarehousePartition(id={self.id!r}, warehouse_id={self.warehouse_id!r})"

class WarehouseObstacle(Base):
    __tablename__ = 'warehouse_obstacle'

    id: Mapped[int] = mapped_column(
        "obstacle_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    name: Mapped[str | None] = mapped_column(
        "obstacle_name",
        String(100),
        nullable=True
    )
    type: Mapped[ObstacleType] = mapped_column(
        "obstacle_type",
        Enum(
            ObstacleType,
            name="obstacle_type",
            native_enum=False
        ),
        nullable=False
    )
    x: Mapped[Decimal] = mapped_column(
        "coord_x",
        Numeric(8, 2),
        nullable=False
    )
    y: Mapped[Decimal] = mapped_column(
        "coord_y",
        Numeric(8, 2),
        nullable=False
    )
    width: Mapped[Decimal] = mapped_column(
        "width",
        Numeric(8, 2),
        nullable=False
    )
    length: Mapped[Decimal] = mapped_column(
        "length",
        Numeric(8, 2),
        nullable=False
    )
    rotation_angle: Mapped[Decimal] = mapped_column(
        "rotation_angle",
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00")
    )
    max_height: Mapped[Decimal | None] = mapped_column(
        "max_height",
        Numeric(8, 2),
        nullable=True
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="obstacles")

    __table_args__ = (
        CheckConstraint(
            "width > 0",
            name="check_obstacle_width_min"
        ),
        CheckConstraint(
            "length > 0",
            name="check_obstacle_length_min"
        ),
        CheckConstraint(
            "rotation_angle >= 0 AND rotation_angle < 360",
            name="check_obstacle_rotation_angle"
        ),
        CheckConstraint(
            "max_height IS NULL OR max_height > 0",
            name="check_obstacle_max_height"
        ),
    )
    
    @validates("width")
    def validate_obstacle_width(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("length")
    def validate_obstacle_length(self, key, value):
        return validate_positive_decimal(key, value)

    @validates("rotation_angle")
    def validate_obstacle_rotation(self, key, value):
        return validate_rotation_angle(key, value)
    
    @validates("max_height")
    def validate_max_height(self, key, value):
        if value is None:
            return None
        return validate_positive_decimal(key, value)

    def __repr__(self) -> str:
        return f"WarehouseObstacle(id={self.id!r}, warehouse_id={self.warehouse_id!r})"

class WarehouseEntryPoint(Base):
    __tablename__ = 'warehouse_entry_point'

    id: Mapped[int] = mapped_column(
        "point_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    point_name: Mapped[str] = mapped_column(
        "point_name",
        String(100),
        nullable=False
    )
    point_type: Mapped[PointType] = mapped_column(
        "point_type",
        Enum(
            PointType,
            name="point_type",
            native_enum=False
        ),
        nullable=False
    )
    x: Mapped[Decimal] = mapped_column(
        "coord_x",
        Numeric(8, 2),
        nullable=False
    )
    y: Mapped[Decimal] = mapped_column(
        "coord_y",
        Numeric(8, 2),
        nullable=False
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="entry_points")

    def __repr__(self) -> str:
        return f"WarehouseEntryPoint(id={self.id!r}, name={self.point_name!r})"

class Zone(Base):
    __tablename__ = 'zone'

    id: Mapped[int] = mapped_column(
        "zone_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        "zone_name",
        String(100),
        nullable=False
    )
    type: Mapped[ZoneType] = mapped_column(
        "zone_type",
        Enum(
            ZoneType,
            name="zone_type",
            native_enum=False
        ),
        nullable=False
    )
    x: Mapped[Decimal] = mapped_column(
        "zone_coord_x",
        Numeric(8, 2),
        nullable=False
    )
    y: Mapped[Decimal] = mapped_column(
        "zone_coord_y",
        Numeric(8, 2),
        nullable=False
    )
    width: Mapped[Decimal] = mapped_column(
        "zone_width",
        Numeric(8, 2),
        nullable=False
    )
    length: Mapped[Decimal] = mapped_column(
        "zone_length",
        Numeric(8, 2),
        nullable=False
    )
    rotation_angle: Mapped[Decimal] = mapped_column(
        "rotation_angle",
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00")
    )
    max_capacity_m3: Mapped[Decimal | None] = mapped_column(
        "max_capacity_m3",
        Numeric(10, 2),
        nullable=True
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="zones")

    __table_args__ = (
        CheckConstraint(
            "zone_width > 0",
            name="check_zone_width_min"
        ),
        CheckConstraint(
            "zone_length > 0",
            name="check_zone_length_min"
        ),
        CheckConstraint(
            "rotation_angle >= 0 AND rotation_angle < 360",
            name="check_zone_rotation_angle"
        ),
        CheckConstraint(
            "max_capacity_m3 IS NULL OR max_capacity_m3 > 0",
            name="check_zone_max_capacity_m3"
        ),
    )
    
    @validates("width")
    def validate_zone_width(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("length")
    def validate_zone_length(self, key, value):
        return validate_positive_decimal(key, value)

    @validates("rotation_angle")
    def validate_zone_rotation(self, key, value):
        return validate_rotation_angle(key, value)

    @validates("max_capacity_m3")
    def validate_max_capacity_m3(self, key, value):
        if value is None:
            return None
        return validate_positive_decimal(key, value)

    def __repr__(self) -> str:
        return f"Zone(id={self.id!r}, name='{self.name!r}')"

class Rack(Base):
    __tablename__ = 'rack'

    id: Mapped[int] = mapped_column(
        "rack_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey(
            "warehouse.warehouse_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    code: Mapped[str] = mapped_column(
        "rack_code",
        String(30),
        nullable=False
    )
    x: Mapped[Decimal] = mapped_column(
        "rack_coord_x",
        Numeric(8, 2),
        nullable=False
    )
    y: Mapped[Decimal] = mapped_column(
        "rack_coord_y",
        Numeric(8, 2),
        nullable=False
    )
    width: Mapped[Decimal] = mapped_column(
        "rack_width",
        Numeric(8, 2),
        nullable=False
    )
    length: Mapped[Decimal] = mapped_column(
        "rack_length",
        Numeric(8, 2),
        nullable=False
    )
    rotation_angle: Mapped[Decimal] = mapped_column(
        "rotation_angle",
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default=text("0.00")
    )
    shelves_count: Mapped[int] = mapped_column(
        "shelves_count",
        Integer,
        nullable=False
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="racks")
    shelves: Mapped[list["Shelf"]] = relationship(
        back_populates="rack",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        CheckConstraint(
            "rack_width > 0",
            name="check_rack_width_min",
        ),
        CheckConstraint(
            "rack_length > 0",
            name="check_rack_length_min",
        ),
        CheckConstraint(
            "rotation_angle >= 0 AND rotation_angle < 360",
            name="check_rack_rotation_angle",
        ),
        CheckConstraint(
            "shelves_count > 0",
            name="check_rack_shelves_count_min",
        ),
    )
    
    @validates("width")
    def validate_rack_width(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("length")
    def validate_rack_length(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("rotation_angle")
    def validate_rack_rotation(self, key, value):
        return validate_rotation_angle(key, value)
    
    @validates("shelves_count")
    def validate_shelves_count(self, key, value):
        if value <= 0:
            raise ValueError(
                f"Атрибут {key!r} має бути >= 1 (отримано: {value!r})"
            )
        return value

    def __repr__(self) -> str:
        return f"Rack(id={self.id!r}, code={self.code!r})"

class Shelf(Base):
    __tablename__ = 'shelf'

    id: Mapped[int] = mapped_column(
        "shelf_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    rack_id: Mapped[int] = mapped_column(
        "rack_id",
        BigInteger,
        ForeignKey(
            "rack.rack_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )
    code: Mapped[str] = mapped_column(
        "shelf_code",
        String(50),
        nullable=False
    )
    qr: Mapped[str] = mapped_column(
        "qr",
        String(100),
        unique=True,
        nullable=False
    )
    width: Mapped[Decimal] = mapped_column(
        "shelf_width",
        Numeric(8, 2),
        nullable=False
    )
    length: Mapped[Decimal] = mapped_column(
        "shelf_length",
        Numeric(8, 2),
        nullable=False
    )
    height: Mapped[Decimal] = mapped_column(
        "shelf_height",
        Numeric(8, 2),
        nullable=False
    )
    max_weight: Mapped[Decimal] = mapped_column(
        "shelf_max_weight",
        Numeric(10, 3),
        nullable=False
    )
    is_occupied: Mapped[bool] = mapped_column(
        "is_occupied",
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )
    status: Mapped[ShelfStatus] = mapped_column(
        "shelf_status",
        Enum(
            ShelfStatus,
            name="shelf_status",
            native_enum=False
        ),
        nullable=False,
        default=ShelfStatus.ACTIVE,
        server_default=ShelfStatus.ACTIVE.value
    )
    inactive_reason: Mapped[InactiveReason | None] = mapped_column(
        "inactive_reason",
        Enum(
            InactiveReason,
            name="inactive_reason",
            native_enum=False
        ),
        nullable=True
    )

    rack: Mapped["Rack"] = relationship(back_populates="shelves")
    
    __table_args__ = (
        CheckConstraint(
            "shelf_width > 0",
            name="check_shelf_width_min",
        ),
        CheckConstraint(
            "shelf_length > 0",
            name="check_shelf_length_min",
        ),
        CheckConstraint(
            "shelf_height > 0",
            name="check_shelf_height_min",
        ),
        CheckConstraint(
            "shelf_max_weight > 0",
            name="check_shelf_max_weight_min",
        ),
        UniqueConstraint(
            "rack_id",
            "shelf_code",
            name = "uq_shelf_rack_code"
        )
    )
    
    @validates("width")
    def validate_shelf_width(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("length")
    def validate_shelf_length(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("height")
    def validate_shelf_height(self, key, value):
        return validate_positive_decimal(key, value)
    
    @validates("max_weight")
    def validate_shelf_max_weight(self, key, value):
        return validate_positive_decimal(key, value)

    def occupy(self) -> None:
        
        if self.status != ShelfStatus.ACTIVE:
            raise ValueError("Не можна розміщувати товар на неактивній полиці.") 
        
        self.is_occupied = True
        
    def release(self) -> None:
        
        
        self.is_occupied = False

    @property
    def total_volume_m3(self) -> float:
        
        return float(self.length) * float(self.width) * float(self.height)

    def __repr__(self) -> str:
        return f"Shelf(id={self.id!r}, code={self.code!r})"

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
        return(
            f"WarehouseTaskStep(id={self.id!r}, "
            f"task_id={self.warehouse_task_id!r}, "
            f"product_id={self.product_id!r})"
        )
