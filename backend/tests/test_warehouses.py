"""Склади: часткове оновлення (PATCH) — стирання адреси та обов'язкові поля."""
from __future__ import annotations

from httpx import AsyncClient

from tests.utils import ADMIN, API, auth, login, unique

WAREHOUSES_URL = f"{API}/warehouses"


async def create_warehouse(client: AsyncClient, token: str) -> dict:
    response = await client.post(
        WAREHOUSES_URL,
        headers=auth(token),
        json={"name": unique("Склад"), "address": "м. Харків, вул. Сумська, 1", "total_area": 500},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_patch_null_address_clears_it(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse(client, token)
    url = f"{WAREHOUSES_URL}/{warehouse['warehouse_id']}"

    # Лише адреса: раніше бекенд вважав тіло порожнім і відповідав 422
    response = await client.patch(url, headers=auth(token), json={"address": None})
    assert response.status_code == 200, response.text
    assert response.json()["warehouse_address"] is None

    loaded = await client.get(url, headers=auth(token))
    assert loaded.json()["warehouse_address"] is None


async def test_patch_null_address_together_with_other_fields(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse(client, token)

    # Раніше назва зберігалася, а стара адреса лишалася
    response = await client.patch(
        f"{WAREHOUSES_URL}/{warehouse['warehouse_id']}",
        headers=auth(token),
        json={"name": "Перейменований склад", "address": None},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["warehouse_name"] == "Перейменований склад"
    assert body["warehouse_address"] is None


async def test_patch_rejects_null_for_required_fields(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse(client, token)
    url = f"{WAREHOUSES_URL}/{warehouse['warehouse_id']}"

    for field in ("name", "total_area"):
        response = await client.patch(url, headers=auth(token), json={field: None})
        assert response.status_code == 422, response.text


async def test_patch_empty_body_is_rejected(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse(client, token)

    response = await client.patch(f"{WAREHOUSES_URL}/{warehouse['warehouse_id']}", headers=auth(token), json={})
    assert response.status_code == 422, response.text
