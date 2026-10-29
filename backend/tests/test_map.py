"""Мапа складу: збереження в БД, стабільні id, права."""
from __future__ import annotations

from httpx import AsyncClient

from tests.utils import ADMIN, API, MANAGER, WORKER, auth, login

MAP_URL = f"{API}/warehouses/1/map"


def map_payload() -> dict:
    return {
        "grid": {"cell_size": 1.0, "grid_width": 40, "grid_height": 20},
        "walls": [
            {"vertex_order": 1, "coord_x": 0, "coord_y": 0},
            {"vertex_order": 2, "coord_x": 40, "coord_y": 0},
            {"vertex_order": 3, "coord_x": 40, "coord_y": 20},
            {"vertex_order": 4, "coord_x": 0, "coord_y": 20},
        ],
        "partitions": [
            {"start_x": 20, "start_y": 0, "end_x": 20, "end_y": 12, "thickness": 0.2, "height": None},
        ],
        "obstacles": [
            {"obstacle_name": "Колона 1", "obstacle_type": "column", "coord_x": 20, "coord_y": 15,
             "width": 1, "length": 1, "rotation_angle": 45, "max_height": None},
        ],
        "entry_points": [
            {"point_name": "Головний вхід", "point_type": "general_entry", "coord_x": 0, "coord_y": 10},
        ],
        "zones": [
            {"zone_name": "Зона приймання", "zone_type": "inbound_dock", "coord_x": 4, "coord_y": 10,
             "width": 20, "length": 8, "rotation_angle": 90, "max_capacity_m3": None},
        ],
        "racks": [
            {"rack_code": "A-01", "coord_x": 12, "coord_y": 2, "width": 1.2, "length": 6,
             "rotation_angle": 0, "shelves_count": 4},
            {"rack_code": "A-02", "coord_x": 12, "coord_y": 5, "width": 1.2, "length": 6,
             "rotation_angle": 0, "shelves_count": 4},
        ],
    }


async def test_map_is_persisted_with_ids(client: AsyncClient):
    token = await login(client, ADMIN)

    saved = await client.put(MAP_URL, headers=auth(token), json=map_payload())
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert all(rack["rack_id"] for rack in body["racks"])
    assert body["partitions"][0]["partition_id"]
    assert body["obstacles"][0]["rotation_angle"] == 45
    assert body["zones"][0]["rotation_angle"] == 90

    loaded = await client.get(MAP_URL, headers=auth(token))
    assert loaded.status_code == 200
    assert loaded.json() == body


async def test_resave_keeps_ids_and_removes_missing(client: AsyncClient):
    token = await login(client, ADMIN)
    first = (await client.put(MAP_URL, headers=auth(token), json=map_payload())).json()

    # Зберігаємо те, що повернув сервер: перший стелаж зсунутий, другий видалений, контур змінено
    second_payload = {**first}
    kept_rack = {**first["racks"][0], "coord_x": 14}
    second_payload["racks"] = [kept_rack]
    second_payload["walls"] = [
        {"vertex_order": 1, "coord_x": 0, "coord_y": 0},
        {"vertex_order": 2, "coord_x": 30, "coord_y": 0},
        {"vertex_order": 3, "coord_x": 0, "coord_y": 20},
    ]

    second = await client.put(MAP_URL, headers=auth(token), json=second_payload)
    assert second.status_code == 200, second.text
    body = second.json()
    assert [rack["rack_id"] for rack in body["racks"]] == [kept_rack["rack_id"]]
    assert body["racks"][0]["coord_x"] == 14
    assert len(body["walls"]) == 3
    assert body["partitions"][0]["partition_id"] == first["partitions"][0]["partition_id"]


async def test_worker_cannot_save_map(client: AsyncClient):
    token = await login(client, WORKER)
    assert (await client.get(MAP_URL, headers=auth(token))).status_code == 200
    assert (await client.put(MAP_URL, headers=auth(token), json=map_payload())).status_code == 403


async def test_manager_can_view_but_not_save_map(client: AsyncClient):
    token = await login(client, MANAGER)
    assert (await client.get(MAP_URL, headers=auth(token))).status_code == 200
    assert (await client.put(MAP_URL, headers=auth(token), json=map_payload())).status_code == 403


async def test_unknown_warehouse_returns_404(client: AsyncClient):
    token = await login(client, ADMIN)
    url = f"{API}/warehouses/999999/map"
    assert (await client.get(url, headers=auth(token))).status_code == 404
    assert (await client.put(url, headers=auth(token), json=map_payload())).status_code == 404
