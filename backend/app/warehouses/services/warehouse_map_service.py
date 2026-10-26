"""Сервіс топології складу: знімок у БД + синхронізація з таблицями."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ObstacleType, PointType, ZoneType
from app.warehouses.models import (
    Rack,
    WarehouseEntryPoint,
    WarehouseMapSnapshot,
    WarehouseObstacle,
    WarehouseWall,
    Zone,
)

MAP_KEYS = ("walls", "partitions", "racks", "obstacles", "zones", "entry_points")


def _decimal(value: Any, fallback: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal(fallback)


def _positive(value: Any, fallback: str = "0.01") -> Decimal:
    parsed = _decimal(value, fallback)
    return parsed if parsed > 0 else Decimal(fallback)


def _empty_map() -> dict[str, list]:
    return {key: [] for key in MAP_KEYS}


def _normalize(payload: dict[str, Any] | None) -> dict[str, list]:
    result = _empty_map()
    if payload:
        for key in MAP_KEYS:
            value = payload.get(key)
            result[key] = list(value) if isinstance(value, list) else []
    return result


class WarehouseMapService:
    """Читає та зберігає топологію складу.

    Повний формат конструктора (включно з перегородками й кутами повороту)
    зберігається як JSON-знімок. Стелажі, зони, перешкоди, стіни та точки
    входу додатково синхронізуються зі своїми таблицями — ними користуються
    дашборд, сторінка складу та полиці стелажів.
    """

    @classmethod
    async def get_map(cls, session: AsyncSession, warehouse_id: int) -> dict[str, Any]:
        snapshot = await session.scalar(
            select(WarehouseMapSnapshot).where(
                WarehouseMapSnapshot.warehouse_id == warehouse_id
            )
        )
        if snapshot is not None:
            return _normalize(snapshot.payload)
        return await cls._derive_from_tables(session, warehouse_id)

    @classmethod
    async def save_map(
        cls,
        session: AsyncSession,
        warehouse_id: int,
        payload: dict[str, Any],
        provided_fields: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        normalized = _normalize(payload)
        provided = set(provided_fields) if provided_fields is not None else set(MAP_KEYS)

        snapshot = await session.scalar(
            select(WarehouseMapSnapshot).where(
                WarehouseMapSnapshot.warehouse_id == warehouse_id
            )
        )
        if snapshot is None:
            snapshot = WarehouseMapSnapshot(
                warehouse_id=warehouse_id,
                payload=normalized,
            )
            session.add(snapshot)
        else:
            snapshot.payload = normalized

        if "walls" in provided:
            await cls._sync_walls(session, warehouse_id, normalized["walls"])
        if "racks" in provided:
            await cls._sync_racks(session, warehouse_id, normalized["racks"])
        if "zones" in provided:
            await cls._sync_zones(session, warehouse_id, normalized["zones"])
        if "entry_points" in provided:
            await cls._sync_entry_points(session, warehouse_id, normalized["entry_points"])
        if "obstacles" in provided:
            await cls._sync_obstacles(session, warehouse_id, normalized["obstacles"])

        await session.commit()
        return normalized

    # ── Синхронізація з таблицями ─────────────────────────────────────────

    @classmethod
    async def _sync_walls(
        cls, session: AsyncSession, warehouse_id: int, walls: list[dict[str, Any]]
    ) -> None:
        await session.execute(
            delete(WarehouseWall).where(WarehouseWall.warehouse_id == warehouse_id)
        )
        ordered = sorted(walls, key=lambda item: int(item.get("vertex_order") or 0))
        for order, wall in enumerate(ordered, start=1):
            session.add(
                WarehouseWall(
                    warehouse_id=warehouse_id,
                    vertex_order=int(wall.get("vertex_order") or order),
                    x=_decimal(wall.get("coord_x")),
                    y=_decimal(wall.get("coord_y")),
                )
            )

    @classmethod
    async def _sync_racks(
        cls, session: AsyncSession, warehouse_id: int, racks: list[dict[str, Any]]
    ) -> None:
        existing = {
            rack.code: rack
            for rack in (
                await session.scalars(
                    select(Rack).where(Rack.warehouse_id == warehouse_id)
                )
            ).all()
        }
        seen: set[str] = set()

        for item in racks:
            code = str(item.get("rack_code") or "").strip()
            if not code:
                continue
            seen.add(code)
            rack = existing.get(code)
            if rack is None:
                rack = Rack(
                    warehouse_id=warehouse_id,
                    code=code,
                    x=_decimal(item.get("coord_x")),
                    y=_decimal(item.get("coord_y")),
                    width=_positive(item.get("width")),
                    length=_positive(item.get("length")),
                    rotation_angle=_decimal(item.get("rotation_angle")),
                    shelves_count=max(1, int(item.get("shelves_count") or 1)),
                )
                session.add(rack)
            else:
                rack.x = _decimal(item.get("coord_x"))
                rack.y = _decimal(item.get("coord_y"))
                rack.width = _positive(item.get("width"))
                rack.length = _positive(item.get("length"))
                rack.rotation_angle = _decimal(item.get("rotation_angle"))
                rack.shelves_count = max(1, int(item.get("shelves_count") or rack.shelves_count))

        for code, rack in existing.items():
            if code not in seen:
                await session.delete(rack)

    @classmethod
    async def _sync_zones(
        cls, session: AsyncSession, warehouse_id: int, zones: list[dict[str, Any]]
    ) -> None:
        existing = {
            zone.name: zone
            for zone in (
                await session.scalars(
                    select(Zone).where(Zone.warehouse_id == warehouse_id)
                )
            ).all()
        }
        seen: set[str] = set()

        for item in zones:
            name = str(item.get("zone_name") or "").strip()
            if not name:
                continue
            seen.add(name)
            try:
                zone_type = ZoneType(str(item.get("zone_type")))
            except ValueError:
                continue

            zone = existing.get(name)
            if zone is None:
                zone = Zone(
                    warehouse_id=warehouse_id,
                    name=name,
                    type=zone_type,
                    x=_decimal(item.get("coord_x")),
                    y=_decimal(item.get("coord_y")),
                    width=_positive(item.get("width")),
                    length=_positive(item.get("length")),
                )
                session.add(zone)
            else:
                zone.type = zone_type
                zone.x = _decimal(item.get("coord_x"))
                zone.y = _decimal(item.get("coord_y"))
                zone.width = _positive(item.get("width"))
                zone.length = _positive(item.get("length"))

            capacity = item.get("max_capacity_m3")
            zone.max_capacity_m3 = _positive(capacity) if capacity not in (None, "") else None

        for name, zone in existing.items():
            if name not in seen:
                await session.delete(zone)

    @classmethod
    async def _sync_entry_points(
        cls, session: AsyncSession, warehouse_id: int, points: list[dict[str, Any]]
    ) -> None:
        existing = {
            point.point_name: point
            for point in (
                await session.scalars(
                    select(WarehouseEntryPoint).where(
                        WarehouseEntryPoint.warehouse_id == warehouse_id
                    )
                )
            ).all()
        }
        seen: set[str] = set()

        for item in points:
            name = str(item.get("point_name") or "").strip()
            if not name:
                continue
            seen.add(name)
            try:
                point_type = PointType(str(item.get("point_type")))
            except ValueError:
                continue

            point = existing.get(name)
            if point is None:
                session.add(
                    WarehouseEntryPoint(
                        warehouse_id=warehouse_id,
                        point_name=name,
                        point_type=point_type,
                        x=_decimal(item.get("coord_x")),
                        y=_decimal(item.get("coord_y")),
                    )
                )
            else:
                point.point_type = point_type
                point.x = _decimal(item.get("coord_x"))
                point.y = _decimal(item.get("coord_y"))

        for name, point in existing.items():
            if name not in seen:
                await session.delete(point)

    @classmethod
    async def _sync_obstacles(
        cls, session: AsyncSession, warehouse_id: int, obstacles: list[dict[str, Any]]
    ) -> None:
        await session.execute(
            delete(WarehouseObstacle).where(WarehouseObstacle.warehouse_id == warehouse_id)
        )
        for item in obstacles:
            try:
                obstacle_type = ObstacleType(str(item.get("obstacle_type")))
            except ValueError:
                continue
            session.add(
                WarehouseObstacle(
                    warehouse_id=warehouse_id,
                    name=item.get("obstacle_name"),
                    type=obstacle_type,
                    x=_decimal(item.get("coord_x")),
                    y=_decimal(item.get("coord_y")),
                    width=_positive(item.get("width")),
                    length=_positive(item.get("length")),
                    max_height=(
                        _positive(item.get("max_height"))
                        if item.get("max_height") not in (None, "")
                        else None
                    ),
                )
            )

    # ── Похідна мапа, якщо знімка ще немає ────────────────────────────────

    @classmethod
    async def _derive_from_tables(
        cls, session: AsyncSession, warehouse_id: int
    ) -> dict[str, Any]:
        walls = (
            await session.scalars(
                select(WarehouseWall)
                .where(WarehouseWall.warehouse_id == warehouse_id)
                .order_by(WarehouseWall.vertex_order)
            )
        ).all()
        racks = (
            await session.scalars(select(Rack).where(Rack.warehouse_id == warehouse_id))
        ).all()
        zones = (
            await session.scalars(select(Zone).where(Zone.warehouse_id == warehouse_id))
        ).all()
        obstacles = (
            await session.scalars(
                select(WarehouseObstacle).where(
                    WarehouseObstacle.warehouse_id == warehouse_id
                )
            )
        ).all()
        points = (
            await session.scalars(
                select(WarehouseEntryPoint).where(
                    WarehouseEntryPoint.warehouse_id == warehouse_id
                )
            )
        ).all()

        return {
            "walls": [
                {
                    "vertex_order": wall.vertex_order,
                    "coord_x": float(wall.x),
                    "coord_y": float(wall.y),
                }
                for wall in walls
            ],
            "partitions": [],
            "racks": [
                {
                    "rack_id": rack.id,
                    "rack_code": rack.code,
                    "coord_x": float(rack.x),
                    "coord_y": float(rack.y),
                    "length": float(rack.length),
                    "width": float(rack.width),
                    "rotation_angle": float(rack.rotation_angle),
                    "shelves_count": rack.shelves_count,
                }
                for rack in racks
            ],
            "obstacles": [
                {
                    "obstacle_id": obstacle.id,
                    "obstacle_name": obstacle.name,
                    "obstacle_type": obstacle.type.value,
                    "coord_x": float(obstacle.x),
                    "coord_y": float(obstacle.y),
                    "length": float(obstacle.length),
                    "width": float(obstacle.width),
                    "rotation_angle": 0.0,
                    "max_height": float(obstacle.max_height) if obstacle.max_height else None,
                }
                for obstacle in obstacles
            ],
            "zones": [
                {
                    "zone_id": zone.id,
                    "zone_name": zone.name,
                    "zone_type": zone.type.value,
                    "coord_x": float(zone.x),
                    "coord_y": float(zone.y),
                    "length": float(zone.length),
                    "width": float(zone.width),
                    "rotation_angle": 0.0,
                    "max_capacity_m3": (
                        float(zone.max_capacity_m3) if zone.max_capacity_m3 else None
                    ),
                }
                for zone in zones
            ],
            "entry_points": [
                {
                    "point_id": point.id,
                    "point_name": point.point_name,
                    "point_type": point.point_type.value,
                    "coord_x": float(point.x),
                    "coord_y": float(point.y),
                }
                for point in points
            ],
        }

    @staticmethod
    def find_path(
        warehouse_id: int,
        start: tuple[float, float],
        target: tuple[float, float],
    ) -> list[tuple[float, float]]:
        """Пошук маршруту ще не реалізовано."""
        raise NotImplementedError("Пошук маршруту ще не реалізовано")
