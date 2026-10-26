from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas import WarehouseMapUpdateSchema
from app.warehouses.models import (
    Rack,
    Warehouse,
    WarehouseEntryPoint,
    WarehouseGrid,
    WarehouseObstacle,
    WarehousePartition,
    WarehouseWall,
    Zone,
)

#колекція мапи -> (модель, поле id у схемі, поле схеми -> атрибут моделі)
#назва колекції збігається з relationship у Warehouse
_COLLECTIONS: dict[str, tuple[type, str, dict[str, str]]] = {
    "partitions": (WarehousePartition, "partition_id", {
        "start_x": "start_x",
        "start_y": "start_y",
        "end_x": "end_x",
        "end_y": "end_y",
        "thickness": "thickness",
        "height": "height",
    }),
    "obstacles": (WarehouseObstacle, "obstacle_id", {
        "obstacle_name": "name",
        "obstacle_type": "type",
        "coord_x": "x",
        "coord_y": "y",
        "width": "width",
        "length": "length",
        "rotation_angle": "rotation_angle",
        "max_height": "max_height",
    }),
    "entry_points": (WarehouseEntryPoint, "point_id", {
        "point_name": "point_name",
        "point_type": "point_type",
        "coord_x": "x",
        "coord_y": "y",
    }),
    "zones": (Zone, "zone_id", {
        "zone_name": "name",
        "zone_type": "type",
        "coord_x": "x",
        "coord_y": "y",
        "width": "width",
        "length": "length",
        "rotation_angle": "rotation_angle",
        "max_capacity_m3": "max_capacity_m3",
    }),
    "racks": (Rack, "rack_id", {
        "rack_code": "code",
        "coord_x": "x",
        "coord_y": "y",
        "width": "width",
        "length": "length",
        "rotation_angle": "rotation_angle",
        "shelves_count": "shelves_count",
    }),
}

_CENTS = Decimal("0.01")


def _to_angle(value: float) -> Decimal:
    """Кут зі схеми (float) -> Numeric(5, 2) у межах [0, 360)."""
    return Decimal(str(value)).quantize(_CENTS) % 360


def _polygon_area(walls: list[WarehouseWall]) -> Decimal:
    """Площа контуру за формулою шнурування (вершини за vertex_order)."""
    pts = [(w.x, w.y) for w in sorted(walls, key=lambda w: w.vertex_order)]
    n = len(pts)
    doubled = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    return (abs(doubled) / 2).quantize(_CENTS)


class WarehouseMapNotFound(Exception):
    """Склад із таким id не існує."""


class WarehouseMapService:
    """Сервіс роботи з картою складу (зберігання в БД)."""

    @staticmethod
    async def _load_warehouse(session: AsyncSession, warehouse_id: int, for_update: bool = False) -> Warehouse:
        query = (
            select(Warehouse)
            .where(Warehouse.id == warehouse_id)
            .options(
                selectinload(Warehouse.grids),
                selectinload(Warehouse.walls),
                *(selectinload(getattr(Warehouse, collection)) for collection in _COLLECTIONS),
            )
        )
        if for_update:
            #блокуємо рядок складу, щоб два одночасні збереження не перемішали топологію
            query = query.with_for_update(of=Warehouse)
        warehouse = await session.scalar(query)
        if warehouse is None:
            raise WarehouseMapNotFound(warehouse_id)
        return warehouse

    @classmethod
    async def get_map(cls, session: AsyncSession, warehouse_id: int) -> dict[str, Any]:
        """Повертає карту складу з БД."""
        warehouse = await cls._load_warehouse(session, warehouse_id)
        return cls._serialize(warehouse)

    @classmethod
    async def save_map(
        cls,
        session: AsyncSession,
        warehouse_id: int,
        map_data: WarehouseMapUpdateSchema,
    ) -> dict[str, Any]:
        """
        PUT повністю замінює топологію. Об'єкти з відомим id оновлюються на місці
        (щоб не губились пов'язані дані, напр. полиці стелажа), без id — створюються,
        відсутні в запиті — видаляються.
        """
        warehouse = await cls._load_warehouse(session, warehouse_id, for_update=True)

        cls._sync_grid(warehouse, map_data)
        cls._sync_walls(warehouse, map_data)
        for collection, (model, id_field, fields) in _COLLECTIONS.items():
            existing = {obj.id: obj for obj in getattr(warehouse, collection)}
            synced = []
            for item in getattr(map_data, collection):
                obj = existing.pop(getattr(item, id_field), None) or model()
                for schema_field, attr in fields.items():
                    value = getattr(item, schema_field)
                    if schema_field == "rotation_angle":
                        value = _to_angle(value)
                    setattr(obj, attr, value)
                synced.append(obj)
            #усе, що не потрапило в synced, видалить cascade delete-orphan
            setattr(warehouse, collection, synced)

        if warehouse.walls:
            area = _polygon_area(warehouse.walls)
            if area > 0:
                warehouse.total_area = area

        await session.commit()
        return cls._serialize(warehouse)

    @staticmethod
    def _sync_grid(warehouse: Warehouse, map_data: WarehouseMapUpdateSchema) -> None:
        """Одна сітка на склад: оновлюємо першу, зайві прибираємо."""
        if map_data.grid is None:
            warehouse.grids = []
            return
        grid = warehouse.grids[0] if warehouse.grids else WarehouseGrid()
        grid.cell_size = map_data.grid.cell_size
        grid.grid_width = map_data.grid.grid_width
        grid.grid_height = map_data.grid.grid_height
        warehouse.grids = [grid]

    @staticmethod
    def _sync_walls(warehouse: Warehouse, map_data: WarehouseMapUpdateSchema) -> None:
        """
        Вершини зіставляються за vertex_order: так не порушується унікальність
        (warehouse_id, vertex_order), бо INSERT нових рядків іде раніше за DELETE старих.
        """
        existing = {wall.vertex_order: wall for wall in warehouse.walls}
        walls = []
        for vertex in map_data.walls:
            wall = existing.pop(vertex.vertex_order, None) or WarehouseWall(vertex_order=vertex.vertex_order)
            wall.x = vertex.coord_x
            wall.y = vertex.coord_y
            walls.append(wall)
        warehouse.walls = walls

    @staticmethod
    def _serialize(warehouse: Warehouse) -> dict[str, Any]:
        grid = warehouse.grids[0] if warehouse.grids else None
        result: dict[str, Any] = {
            "warehouse_id": warehouse.id,
            "grid": None if grid is None else {
                "cell_size": grid.cell_size,
                "grid_width": grid.grid_width,
                "grid_height": grid.grid_height,
            },
            "walls": [
                {"vertex_order": w.vertex_order, "coord_x": w.x, "coord_y": w.y}
                for w in sorted(warehouse.walls, key=lambda w: w.vertex_order)
            ],
        }
        for collection, (_, id_field, fields) in _COLLECTIONS.items():
            result[collection] = [
                {
                    id_field: obj.id,
                    **{schema_field: getattr(obj, attr) for schema_field, attr in fields.items()},
                }
                for obj in sorted(getattr(warehouse, collection), key=lambda o: o.id)
            ]
        return result

    @staticmethod
    def find_path(
        warehouse_id: int,
        start: tuple[float, float],
        target: tuple[float, float],
    ) -> list[tuple[float, float]]:
        """Ти думав тут щось буде?"""
        raise NotImplementedError("Пошук маршруту ще не реалізовано")
    # ⡅⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⢀⡀⢀⢀⡀⢀⡀⢀⡀⢀⢈⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡈⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣃⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣤⣄⣫⣝⣫⣝⣭⣭⣯⣹⡇
    # ⠅⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⡀⠠⡀⡀⡀⡀⠠⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠨⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣵⣿⣏⡮⢽⣯⣹⡅
    # ⡂⡀⢀⢀⢀⡀⡀⡀⢀⢀⡀⢂⡀⢐⡀⢐⡂⢀⡀⢀⡀⢂⡀⢀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢂⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣾⣿⣿⣿⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣻⣷⣿⣟⡳⣻⡇
    # ⠅⡀⡀⡀⡀⡀⡀⡀⠄⡀⡀⠁⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠨⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⡿⠊⠑⠾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣻⡷⢽⡽⠆
    # ⡆⡀⡀⡀⠠⡀⡀⠐⡐⡀⡀⠠⠠⠄⠠⡠⡐⠄⡀⡀⡀⠢⢄⠆⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠰⡀⡇⠠⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣷⣽⣿⠇⡀⡀⡀⠠⠚⠗⡻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠐⢪⢇⣺⡖⡂
    # ⡅⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⡀⡂⢀⡀⡀⢄⡐⠠⡐⠄⠐⠈⠐⡀⡀⠄⡀⡀⡀⠠⡀⡀⡀⡀⡀⡀⡀⡀⢐⡀⡇⢈⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⡀⡀⡀⡀⡀⡀⠐⢐⠛⣿⠈⡈⡉⠉⢃⠙⢿⣿⣿⡘⡣⠦⡍⣸⠆
    # ⡃⡀⡀⡀⠈⠈⠑⠁⠈⠁⡀⡀⡀⠁⡂⢈⡁⡀⡀⢁⢌⣈⢈⠌⠂⢡⣷⣿⣿⣦⢀⠈⡀⡀⡀⡀⡀⡀⡀⠨⡀⡇⢀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣟⡀⡀⡀⡀⡀⡀⡀⡀⡀⠐⠁⡀⢈⠂⡀⡀⡀⢘⣿⣿⢂⣳⣟⣿⣿⡇
    # ⠂⡀⠅⠁⣀⣤⣴⣶⣿⣿⣿⣿⣤⠐⠆⡰⡀⣿⢓⠬⠐⠠⠢⠦⣽⣿⣿⣿⣿⣿⣿⣧⡀⡀⡀⡀⡀⡀⡀⢐⡀⡇⠨⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡇⢸⠇⡀⡀⡀⢠⣄⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢸⢟⠟⣵⣷⣿⣿⣿⡇
    # ⡶⢟⣯⣳⣱⢿⣿⣿⣿⣿⣿⣿⣿⣿⢤⣤⡰⠽⣡⣿⢿⢻⣎⣫⣿⢿⣿⣿⣿⣿⣿⣿⣷⡀⡀⠄⡀⡀⡀⠨⡀⡇⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⢠⣾⡀⡀⡀⣤⢄⣀⠈⠙⠦⡀⡀⡀⠤⠹⠻⠿⢦⡀⡾⣾⣾⣷⣿⣿⣿⣿⡇
    # ⣷⣳⣷⣳⣾⣖⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⢁⣼⡻⣟⣳⡾⠮⣿⣿⣿⣿⣿⣿⣿⣳⣿⣧⡀⡀⡀⡀⡀⢰⡀⡧⡀⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠈⡗⡀⡀⡀⡀⡀⠈⠐⣛⠂⡀⡀⢀⡔⣤⡤⢀⡀⠐⣾⣟⣾⣿⣿⣿⣿⣿⡇
    # ⣗⣾⣿⣟⣿⣗⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣗⣪⣥⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⣿⣿⡀⠐⢀⡀⡀⢐⡀⣗⢰⠘⡀⠐⡀⡄⡀⣀⣀⡠⠤⠄⠒⠒⣠⡀⡃⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠈⠉⡀⡞⠉⠛⠛⠿⣿⣯⣿⣿⡇
    # ⣿⣿⣿⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣷⠂⡀⡀⡀⡀⡀⣯⢸⡀⡀⡀⡀⡀⡀⡀⡀⡀⣤⣤⣾⣿⣿⡇⠁⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠃⡀⡀⡀⡀⡀⡀⡀⠐⠁
    # ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⣿⣯⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠐⡀⡀⢘⡀⣿⢸⠘⡀⠦⣄⣤⣾⣿⣿⣿⣿⣿⣿⣿⣿⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⡀⡀⡀⡀⡀⡀⡀⡀⡸⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀
    # ⣿⣿⣿⣿⣿⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣯⣿⣿⣯⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡋⠁⡀⠠⠄⠠⠠⠨⡀⢿⠸⢈⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⡇⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⠁⡀⡀⡀⡀⠠⠄⡀⡀⡀⡀
    # ⠛⠛⠛⠛⡛⣹⠻⣿⣿⣿⣿⣿⣿⡟⣿⣿⣿⣿⣾⣿⣭⢴⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠐⡀⠄⡀⠠⠐⡀⢩⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠹⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⡦⡀⡀⡀⣌⡀⡀⠠⠄⠈⡀⡀⠄⡀⡀⠂
    # ⣦⣾⣿⣿⣿⠍⡨⠈⣭⢭⡭⢍⡟⣿⣿⣭⣽⢿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠠⠄⡀⠨⡀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⡀⢿⡀⡀⡀⡀⠉⠙⠶⠶⠦⠄⠍⡀⡀⠸⣿⣷⣄⡀⡀⡀⡀⡀⡀⡀⡀⠁
    # ⣿⣟⢝⡷⠛⡇⣹⣐⡨⣧⣮⣵⣽⣿⢌⢇⣛⡋⣋⣙⣛⣛⣛⡛⠛⠳⠹⣿⣿⣿⣿⣿⣿⡿⢐⠨⡀⡀⠘⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⡀⢿⡠⡀⡀⡀⡀⡀⡀⡀⡀⡀⣴⡀⡀⠈⣿⣿⣿⣄⡀⡀⡀⡀⣠⣤⡁
    # ⣏⡣⣿⢛⣹⠣⣧⢿⡇⢏⠻⡺⠿⡳⡻⠯⢿⣾⡷⡳⢷⣾⢾⡩⣓⣤⢶⣾⣿⡆⣿⣿⣿⠠⠨⠌⠌⢠⡀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣄⡀⠻⣆⡀⡀⡀⡀⡀⣴⣀⣾⣿⣷⡀⡀⡀⢸⣿⣿⣿⣤⠺⣽⠻⠄⠃
    # ⣯⠚⡣⡀⣼⡥⣿⡼⡷⣱⠒⠙⠛⠺⣻⣿⣿⣯⠼⠯⠽⢦⣮⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠨⡨⢌⠄⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣄⣉⣲⣴⣦⣽⣾⠏⡀⠙⢿⡀⡀⡀⡀⣿⣿⣿⣿⣿⡄⡀⠉⠃
    # ⣟⡀⡏⡀⣿⣪⡿⣫⣭⣧⣾⣶⣳⣭⣽⣿⣿⣿⣿⣿⣿⣿⠿⠟⣉⣩⣬⣍⠿⣿⣿⣿⣿⣿⣄⡌⢌⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⢠⡀⡀⡀⠁⡀⡀⡀⢹⣿⣿⣿⣿⣿⡀⡀⡀
    # ⣿⣻⡤⡐⣿⣿⣃⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣝⢻⣋⣜⣞⣳⣾⣞⣺⣿⣹⣿⣿⣿⢘⡀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⡀⠈⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⣿⣿⣿⡀⠂
    # ⣿⢸⣷⣳⣿⣿⣿⣿⣿⡿⣻⣻⡿⣿⣿⣿⣿⣼⣿⣿⡿⣿⣺⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡏⡀⠂⡀⡀⡀⡀⡀⡀⡀⡀⡀⢿⣿⣿⣿⣿⣿⡟⠆
    # ⣟⡼⣻⣿⣿⣿⣿⣛⣫⣽⣯⣿⡯⢟⣿⣯⣿⣿⣽⣯⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⡏⡶⡄⡀⡀⡀⡀⡀⡀⡀⡀⡀⡀⣼⣿⣿⣿⣿⣿⣧⡀
    # ⣽⣿⣿⣿⣿⠿⠽⢽⣯⣭⣽⣷⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣒⣿⣿⣿⣿⣿⣿⣿⣿⣿⢡⡟⣠⠧⠄⡀⡀⡀⡀⡀⡀⡀⡀⡀⢀⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⡿⣯⣺⣳⣷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢹⠛⢿⠿⣧⡟⣿⣿⣿⣿⢧⢱⠁⡀⡅⡇⡀⡀⡀⡀⡀⡀⡀⡀⡀⣼⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⣿⣿⣿⣟⣿⣿⣿⣿⣹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢰⣰⣡⣿⣸⣿⢳⣷⣿⣿⡏⣼⡟⠸⣰⠷⢻⡀⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⣿⡿⣽⣿⣷⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣿⣿⣿⣬⣼⡇⡀⣿⡇⣘⣷⡀⡀⡀⡀⡀⡀⡀⡀⠸⣿⣿⣿⣿⣿⣿⣿⡀
    # ⣿⣿⣳⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⣼⣿⣟⣥⣧⣷⣿⣿⣯⠠⢸⢻⡀⣿⣾⣷⡀⡀⡀⡀⡀⡀⡀⡀⣿⣿⣿⣿⣿⣿⡿⡀
    # ⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠻⠿⠟⠛⠛⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠷⠿⠿⠿⠿⠰⠾⠿⠫⠿⠿⠿⠿⡀⡀⡀⡀⡀⡀⡀⠘⠿⠿⠿⠿⠿⠧⠇
