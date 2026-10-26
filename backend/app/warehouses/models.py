from decimal import Decimal
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    func,
    text
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
)
from app.core.db import Base


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
    map_snapshot: Mapped["WarehouseMapSnapshot | None"] = relationship(
        back_populates="warehouse",
        cascade="all, delete-orphan",
        uselist=False
    )
    
    __table_args__ = (
        CheckConstraint(
            "total_warehouse_area > 0",
            name="check_warehouse_total_area_min"
        ),
    )
    
    @validates("total_warehouse_area")
    def validate_total_warehouse_area(self, key, value):
        if value is not None and value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be positive (obtained: {value!r})"
            )
        return value
    
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
    
    @staticmethod
    def _validate_positive_decimal(key, value) -> Decimal:
        if value is None:
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            decimal_value: Decimal = Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if decimal_value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        
        return decimal_value
        
    @validates("cell_size")
    def validate_cell_size(self, key, value):
        return self._validate_positive_decimal(key, value)

    @validates("grid_width")
    def validate_grid_width(self, key, value):
        return self._validate_positive_decimal(key, value)

    @validates("grid_height")
    def validate_grid_height(self, key, value):
        return self._validate_positive_decimal(key, value)
    
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
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            integer_value: int = int(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if integer_value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        
        return integer_value

    def __repr__(self) -> str:
        return f"WarehouseWall(id={self.id!r}, vertex_order={self.vertex_order!r})"

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
            "max_height IS NULL OR max_height > 0",
            name="check_obstacle_max_height"
        ),
    )
    
    @staticmethod
    def _validate_positive_decimal(key, value) -> Decimal:
        if value is None:
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            decimal_value: Decimal = Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if decimal_value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        
        return decimal_value
    
    @validates("width")
    def validate_obstacle_width(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("length")
    def validate_obstacle_length(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("max_height")
    def validate_max_height(self, key, value):
        if value is None:
            return None
        if value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        return value

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
            "max_capacity_m3 IS NULL OR max_capacity_m3 > 0",
            name="check_zone_max_capacity_m3"
        ),
    )
    
    @staticmethod
    def _validate_positive_decimal(key, value) -> Decimal:
        if value is None:
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            decimal_value: Decimal = Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if decimal_value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        
        return decimal_value
    
    @validates("zone_width")
    def validate_zone_width(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("zone_length")
    def validate_zone_length(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("max_capacity_m3")
    def validate_max_capacity_m3(self, key, value):
        if value is None:
            return None
        if value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        return value

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
    
    @staticmethod
    def _validate_positive_decimal(key, value) -> Decimal:
        if value is None:
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            decimal_value: Decimal = Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if decimal_value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        
        return decimal_value
    
    @validates("rack_width")
    def validate_rack_width(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("rack_length")
    def validate_rack_length(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("rotation_angle")
    def validate_rotation_angle(self, key, value):
        if value is None:
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            rotation_angle_value: Decimal = Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if rotation_angle_value < 0 or rotation_angle_value >= 360:
            raise ValueError(
                f"Error: attribute {key!r} value must be in range [0, 360) (obtained: {value!r})"
            )
        
        return rotation_angle_value
    
    @validates("shelves_count")
    def validate_shelves_count(self, key, value):
        if value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} min value must be 1 (obtained: {value!r})"
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
        unique=True,
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
    )
    
    @staticmethod
    def _validate_positive_decimal(key, value) -> Decimal:
        if value is None:
            raise ValueError(f"Error: attribute {key!r} cannot be None")
        
        try:
            decimal_value: Decimal = Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"Error: attribute {key!r} must be a valid number (obtained: {value!r})"
            )
        
        if decimal_value <= 0:
            raise ValueError(
                f"Error: attribute {key!r} value must be a positive (obtained: {value!r})"
            )
        
        return decimal_value
    
    @validates("shelf_width")
    def validate_shelf_width(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("shelf_length")
    def validate_shelf_length(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("shelf_height")
    def validate_shelf_height(self, key, value):
        return self._validate_positive_decimal(key, value)
    
    @validates("shelf_max_weight")
    def validate_shelf_max_weight(self, key, value):
        return self._validate_positive_decimal(key, value)

    def occupy(self):
        self.is_occupied = True
        self.status = ShelfStatus.OCCUPIED

    @property
    def total_volume_m3(self) -> float:
        """
        Total shelf volume in cubic meters (m³).
        Provided that the data is stored in mm.
        """
        total_volume_mm: float = float(self.length) * float(self.width) * float(self.height)
        return total_volume_mm / 1_000_000_000

    def __repr__(self) -> str:
        return f"Shelf(id={self.id!r}, code={self.code!r})"

class WarehouseMapSnapshot(Base):
    """Збережена топологія складу в форматі конструктора (JSON).

    Окремий знімок дозволяє зберегти перегородки й кути повороту, для яких
    ще немає окремих таблиць. Стелажі, зони та точки входу додатково
    синхронізуються зі своїми таблицями, щоб ними користувалися дашборд і
    сторінка стелажа.
    """

    __tablename__ = 'warehouse_map'

    id: Mapped[int] = mapped_column(
        "warehouse_map_id",
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        "warehouse_id",
        BigInteger,
        ForeignKey("warehouse.warehouse_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    payload: Mapped[dict] = mapped_column(
        "payload",
        JSON,
        nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="map_snapshot")

    def __repr__(self) -> str:
        return f"WarehouseMapSnapshot(warehouse_id={self.warehouse_id!r})"
