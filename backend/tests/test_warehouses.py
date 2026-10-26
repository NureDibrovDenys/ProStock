"""Картка складу, стелажі та дашборд."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.db import async_session_maker
from app.core.enums import PointType, ShelfStatus, ZoneType
from app.warehouses.models import Rack, Shelf, Warehouse, WarehouseEntryPoint, Zone
from tests.utils import ADMIN, API, WORKER, auth, login, unique


async def create_demo_warehouse() -> tuple[int, str]:
    code = unique("R")
    async with async_session_maker() as session:
        warehouse = Warehouse(
            name="Тестовий склад",
            address="Київ",
            total_area=Decimal("500.00"),
        )
        session.add(warehouse)
        await session.flush()

        rack = Rack(
            warehouse_id=warehouse.id,
            code=code,
            x=Decimal("5"),
            y=Decimal("5"),
            width=Decimal("2.70"),
            length=Decimal("1.10"),
            rotation_angle=Decimal("0"),
            shelves_count=2,
        )
        session.add(rack)
        await session.flush()

        session.add_all(
            [
                Shelf(
                    rack_id=rack.id,
                    code=f"{code}-1",
                    qr=f"QR:{code}-1",
                    width=Decimal("1"),
                    length=Decimal("1"),
                    height=Decimal("0.4"),
                    max_weight=Decimal("100"),
                    is_occupied=True,
                    status=ShelfStatus.OCCUPIED,
                ),
                Shelf(
                    rack_id=rack.id,
                    code=f"{code}-2",
                    qr=f"QR:{code}-2",
                    width=Decimal("1"),
                    length=Decimal("1"),
                    height=Decimal("0.4"),
                    max_weight=Decimal("100"),
                    is_occupied=False,
                    status=ShelfStatus.ACTIVE,
                ),
            ]
        )
        session.add(
            Zone(
                warehouse_id=warehouse.id,
                name="Зона зберігання",
                type=ZoneType.STORAGE_AREA,
                x=Decimal("0"),
                y=Decimal("0"),
                width=Decimal("10"),
                length=Decimal("10"),
            )
        )
        session.add(
            WarehouseEntryPoint(
                warehouse_id=warehouse.id,
                point_name="Вхід",
                point_type=PointType.GENERAL_ENTRY,
                x=Decimal("0"),
                y=Decimal("5"),
            )
        )
        await session.commit()
        return warehouse.id, code


async def test_warehouse_card(client: AsyncClient):
    warehouse_id, _ = await create_demo_warehouse()
    token = await login(client, ADMIN)

    response = await client.get(f"{API}/warehouses/{warehouse_id}", headers=auth(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["warehouse_name"] == "Тестовий склад"
    assert data["total_warehouse_area"] == 500.0

    missing = await client.get(f"{API}/warehouses/999999", headers=auth(token))
    assert missing.status_code == 404


async def test_warehouse_racks_and_rack_details(client: AsyncClient):
    warehouse_id, rack_code = await create_demo_warehouse()
    token = await login(client, ADMIN)

    racks = await client.get(f"{API}/warehouses/{warehouse_id}/racks", headers=auth(token))
    assert racks.status_code == 200, racks.text
    items = racks.json()
    assert len(items) == 1
    assert items[0]["rack_code"] == rack_code
    assert items[0]["shelves_count"] == 2
    assert items[0]["fill_percent"] == 50

    details = await client.get(
        f"{API}/warehouses/{warehouse_id}/racks/{rack_code}", headers=auth(token)
    )
    assert details.status_code == 200, details.text
    data = details.json()
    assert data["rack_code"] == rack_code
    assert len(data["shelves"]) == 2
    assert {shelf["shelf_status"] for shelf in data["shelves"]} == {"occupied", "active"}

    missing = await client.get(
        f"{API}/warehouses/{warehouse_id}/racks/NOPE", headers=auth(token)
    )
    assert missing.status_code == 404


async def test_dashboard_structure(client: AsyncClient):
    warehouse_id, rack_code = await create_demo_warehouse()
    token = await login(client, ADMIN)

    response = await client.get(
        f"{API}/warehouses/{warehouse_id}/dashboard", headers=auth(token)
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["racks_count"] == 1
    assert data["zones_count"] == 1
    assert data["fill_percent"] == 50
    assert data["total_area_m2"] == 500.0
    assert 0 <= data["free_area_m2"] <= 500
    assert data["employees_total"] >= 1
    assert data["rack_fill"][0]["rack_code"] == rack_code
    assert data["recent_operations"] == []


async def test_worker_can_read_warehouse(client: AsyncClient):
    warehouse_id, _ = await create_demo_warehouse()
    token = await login(client, WORKER)

    assert (
        await client.get(f"{API}/warehouses/{warehouse_id}", headers=auth(token))
    ).status_code == 200
    assert (
        await client.get(f"{API}/warehouses/{warehouse_id}/dashboard", headers=auth(token))
    ).status_code == 200
    assert (
        await client.get(f"{API}/warehouses/{warehouse_id}/racks", headers=auth(token))
    ).status_code == 200


async def test_warehouse_requires_auth(client: AsyncClient):
    assert (await client.get(f"{API}/warehouses/1")).status_code == 401
    assert (await client.get(f"{API}/warehouses/1/dashboard")).status_code == 401
