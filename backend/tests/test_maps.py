"""Топологія складу: читання, збереження, синхронізація та права."""
from __future__ import annotations

from httpx import AsyncClient

from tests.test_warehouses import create_demo_warehouse
from tests.utils import ADMIN, API, WORKER, auth, login


async def test_map_returns_warehouse_topology(client: AsyncClient):
    warehouse_id, rack_code = await create_demo_warehouse()
    token = await login(client, ADMIN)

    response = await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["racks"]) == 1
    assert data["racks"][0]["rack_code"] == rack_code
    assert len(data["zones"]) == 1
    assert len(data["entry_points"]) == 1
    # Контур складу в тестовій фікстурі не створюється
    assert data["walls"] == []


async def test_map_save_persists_and_syncs_tables(client: AsyncClient):
    warehouse_id, rack_code = await create_demo_warehouse()
    token = await login(client, ADMIN)

    current = (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    ).json()
    new_code = f"{rack_code}-NEW"
    current["racks"].append(
        {
            "rack_code": new_code,
            "coord_x": 15,
            "coord_y": 7,
            "length": 2.5,
            "width": 1.0,
            "rotation_angle": 90,
            "shelves_count": 3,
        }
    )
    current["walls"] = [
        {"vertex_order": 1, "coord_x": 0, "coord_y": 0},
        {"vertex_order": 2, "coord_x": 30, "coord_y": 0},
        {"vertex_order": 3, "coord_x": 30, "coord_y": 20},
        {"vertex_order": 4, "coord_x": 0, "coord_y": 20},
    ]

    saved = await client.put(
        f"{API}/warehouses/{warehouse_id}/map", headers=auth(token), json=current
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["racks"]) == 2

    # Знімок зберігається між запитами
    again = await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    assert {rack["rack_code"] for rack in again.json()["racks"]} == {rack_code, new_code}
    assert len(again.json()["walls"]) == 4

    # Стелажі синхронізовані з таблицею — їх бачить дашборд і сторінка складу
    racks = await client.get(f"{API}/warehouses/{warehouse_id}/racks", headers=auth(token))
    assert {rack["rack_code"] for rack in racks.json()} == {rack_code, new_code}

    dashboard = await client.get(
        f"{API}/warehouses/{warehouse_id}/dashboard", headers=auth(token)
    )
    assert dashboard.json()["racks_count"] == 2


async def test_map_update_removes_missing_objects(client: AsyncClient):
    warehouse_id, rack_code = await create_demo_warehouse()
    token = await login(client, ADMIN)

    current = (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    ).json()
    current["racks"] = []

    saved = await client.put(
        f"{API}/warehouses/{warehouse_id}/map", headers=auth(token), json=current
    )
    assert saved.status_code == 200
    assert saved.json()["racks"] == []

    racks = await client.get(f"{API}/warehouses/{warehouse_id}/racks", headers=auth(token))
    assert racks.json() == []


async def test_map_write_requires_manager_role(client: AsyncClient):
    warehouse_id, _ = await create_demo_warehouse()
    manager_token = await login(client, ADMIN)
    worker_token = await login(client, WORKER)

    payload = {"walls": [], "partitions": [], "racks": [], "obstacles": [], "zones": [], "entry_points": []}

    assert (
        await client.put(
            f"{API}/warehouses/{warehouse_id}/map", headers=auth(worker_token), json=payload
        )
    ).status_code == 403

    # Читання дозволене комірнику
    assert (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(worker_token))
    ).status_code == 200

    # Запис дозволений адміністратору
    assert (
        await client.put(
            f"{API}/warehouses/{warehouse_id}/map", headers=auth(manager_token), json=payload
        )
    ).status_code == 200


async def test_map_unknown_warehouse_and_auth(client: AsyncClient):
    assert (await client.get(f"{API}/warehouses/999999/map")).status_code == 401

    token = await login(client, ADMIN)
    assert (
        await client.get(f"{API}/warehouses/999999/map", headers=auth(token))
    ).status_code == 404
    assert (
        await client.put(f"{API}/warehouses/999999/map", headers=auth(token), json={})
    ).status_code == 404


async def test_map_preserves_partitions_obstacles_and_capacity(client: AsyncClient):
    warehouse_id, _ = await create_demo_warehouse()
    token = await login(client, ADMIN)

    current = (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    ).json()
    current["partitions"] = [
        {
            "start_x": 5,
            "start_y": 5,
            "end_x": 5,
            "end_y": 15,
            "thickness": 0.2,
            "height": None,
        }
    ]
    current["obstacles"] = [
        {
            "obstacle_name": "Колона",
            "obstacle_type": "column",
            "coord_x": 20,
            "coord_y": 10,
            "length": 1,
            "width": 1,
            "rotation_angle": 0,
            "max_height": 6,
        }
    ]
    current["zones"][0]["max_capacity_m3"] = 120
    current["zones"][0]["rotation_angle"] = 15

    saved = await client.put(
        f"{API}/warehouses/{warehouse_id}/map", headers=auth(token), json=current
    )
    assert saved.status_code == 200, saved.text

    again = (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    ).json()
    assert len(again["partitions"]) == 1
    assert again["partitions"][0]["thickness"] == 0.2
    assert len(again["obstacles"]) == 1
    assert again["obstacles"][0]["obstacle_type"] == "column"
    assert again["zones"][0]["max_capacity_m3"] == 120
    assert again["zones"][0]["rotation_angle"] == 15


async def test_map_rejects_invalid_enum_values(client: AsyncClient):
    warehouse_id, _ = await create_demo_warehouse()
    token = await login(client, ADMIN)

    current = (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    ).json()
    current["zones"][0]["zone_type"] = "not-a-zone"

    response = await client.put(
        f"{API}/warehouses/{warehouse_id}/map", headers=auth(token), json=current
    )
    assert response.status_code == 422, response.text

    # Невдалий запит не змінив збережену мапу
    again = (
        await client.get(f"{API}/warehouses/{warehouse_id}/map", headers=auth(token))
    ).json()
    assert again["zones"][0]["zone_type"] == "storage_area"
