"""Схеми складу: картка складу, стелажі, дашборд."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ObstacleType, PointType, ZoneType


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warehouse_id: int
    warehouse_name: str
    warehouse_address: str | None = None
    total_warehouse_area: float


class RackSummarySchema(BaseModel):
    rack_id: int
    rack_code: str
    shelves_count: int
    fill_percent: int


class ShelfInfoSchema(BaseModel):
    shelf_id: int
    shelf_code: str
    product_name: str | None = None
    occupied: int
    capacity: int
    shelf_status: str


class RackDetailsSchema(BaseModel):
    rack_id: int
    rack_code: str
    zone_name: str | None = None
    updated_at: datetime
    shelves: list[ShelfInfoSchema]


class RackFillSchema(BaseModel):
    rack_id: int
    rack_code: str
    fill_percent: int


class OperationSchema(BaseModel):
    log_id: int
    timestamp: datetime
    action: str


class DashboardStatsSchema(BaseModel):
    racks_count: int
    zones_count: int
    fill_percent: int
    fill_change_week: int
    on_shift: int
    employees_total: int
    free_area_m2: float
    total_area_m2: float
    updated_at: datetime
    rack_fill: list[RackFillSchema]
    recent_operations: list[OperationSchema]


# ── Топологія складу (формат конструктора) ────────────────────────────────

class WallVertexSchema(BaseModel):
    vertex_order: int
    coord_x: float
    coord_y: float


class PartitionSchema(BaseModel):
    partition_id: int | None = None
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    thickness: float = 0.2
    height: float | None = None


class MapRackSchema(BaseModel):
    rack_id: int | None = None
    rack_code: str
    coord_x: float
    coord_y: float
    length: float
    width: float
    rotation_angle: float = 0.0
    shelves_count: int = 1


class MapObstacleSchema(BaseModel):
    obstacle_id: int | None = None
    obstacle_name: str | None = None
    obstacle_type: ObstacleType
    coord_x: float
    coord_y: float
    length: float
    width: float
    rotation_angle: float = 0.0
    max_height: float | None = None


class MapZoneSchema(BaseModel):
    zone_id: int | None = None
    zone_name: str
    zone_type: ZoneType
    coord_x: float
    coord_y: float
    length: float
    width: float
    rotation_angle: float = 0.0
    max_capacity_m3: float | None = None


class MapEntryPointSchema(BaseModel):
    point_id: int | None = None
    point_name: str
    point_type: PointType
    coord_x: float
    coord_y: float


class WarehouseMapSchema(BaseModel):
    walls: list[WallVertexSchema] = Field(default_factory=list)
    partitions: list[PartitionSchema] = Field(default_factory=list)
    racks: list[MapRackSchema] = Field(default_factory=list)
    obstacles: list[MapObstacleSchema] = Field(default_factory=list)
    zones: list[MapZoneSchema] = Field(default_factory=list)
    entry_points: list[MapEntryPointSchema] = Field(default_factory=list)
