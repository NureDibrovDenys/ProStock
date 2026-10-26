"""Спільні хелпери тестів."""
from __future__ import annotations

import uuid

from httpx import AsyncClient

API = "/api/v1"

ADMIN = ("admin@prostock.com", "Admin12345")
MANAGER = ("manager@prostock.com", "Manager12345")
WORKER = ("worker@prostock.com", "Worker12345")


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def login(client: AsyncClient, credentials: tuple[str, str]) -> str:
    response = await client.post(
        f"{API}/auth/login",
        json={"email": credentials[0], "password": credentials[1]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_category(client: AsyncClient, token: str, name: str | None = None) -> int:
    response = await client.post(
        f"{API}/categories",
        headers=auth(token),
        json={"name": name or unique("Категорія")},
    )
    assert response.status_code == 201, response.text
    return response.json()["category_id"]


def product_payload(category_id: int, sku: str | None = None) -> dict:
    return {
        "sku_code": sku or unique("SKU"),
        "name": "Тестовий товар",
        "category_id": category_id,
        "unit_of_measure": "pcs",
        "width": 0.2,
        "length": 0.3,
        "height": 0.1,
        "weight": 0.5,
        "min_stock_level": 3,
    }
