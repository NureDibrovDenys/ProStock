
from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.core.db import async_session_maker
from app.core.enums import ShelfStatus
from app.warehouses.models import Rack, Shelf, Warehouse

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

async def create_supplier(client: AsyncClient, token: str, **overrides) -> int:
    payload = {
        "company_name": unique("ТОВ «Постачальник»"),
        "tax_id": None,
        "contact_person": "Іван Іванович",
        "phone_number": "+380501234567",
        "email": unique("supplier") + "@example.com",
        "address": "м. Київ, вул. Хрещатик, 1",
    }
    payload.update(overrides)
    response = await client.post(
        f"{API}/suppliers", headers=auth(token), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["supplier_id"]

async def create_recipient(client: AsyncClient, token: str, **overrides) -> int:
    payload = {
        "company_name": unique("ТОВ «Одержувач»"),
        "tax_id": None,
        "contact_person": "Петро Петрович",
        "phone_number": "+380509876543",
        "email": unique("recipient") + "@example.com",
        "address": "м. Львів, вул. Городоцька, 2",
    }
    payload.update(overrides)
    response = await client.post(
        f"{API}/recipients", headers=auth(token), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["recipient_id"]

async def create_product(
    client: AsyncClient,
    token: str,
    category_id: int,
    **overrides,
) -> int:
    payload = product_payload(category_id)
    payload.update(overrides)
    response = await client.post(
        f"{API}/products", headers=auth(token), json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()["product_id"]

async def create_warehouse_with_shelves(
    shelves: list[dict] | None = None,
    *,
    rack_code: str | None = None,
    rack_shelves_count: int | None = None,
) -> dict:
    
    shelf_specs = shelves or [
        {
            "code": "S-1",
            "width": Decimal("2.0"),
            "length": Decimal("1.0"),
            "height": Decimal("1.0"),
            "max_weight": Decimal("500"),
        }
    ]
    code = rack_code or unique("R")
    count = rack_shelves_count if rack_shelves_count is not None else len(shelf_specs)

    async with async_session_maker() as session:
        warehouse = Warehouse(
            name=unique("Склад"),
            total_area=Decimal("100.00"),
        )
        session.add(warehouse)
        await session.flush()

        rack = Rack(
            warehouse_id=warehouse.id,
            code=code,
            x=Decimal("1.0"),
            y=Decimal("1.0"),
            width=Decimal("1.0"),
            length=Decimal("2.0"),
            rotation_angle=Decimal("0"),
            shelves_count=count,
        )
        session.add(rack)
        await session.flush()

        shelf_ids: list[int] = []
        for index, spec in enumerate(shelf_specs, start=1):
            shelf_code = spec.get("code") or f"{code}-{index}"
            shelf = Shelf(
                rack_id=rack.id,
                code=shelf_code,
                qr=unique("QR"),
                width=Decimal(str(spec.get("width", 2))),
                length=Decimal(str(spec.get("length", 1))),
                height=Decimal(str(spec.get("height", 1))),
                max_weight=Decimal(str(spec.get("max_weight", 500))),
                status=spec.get("status", ShelfStatus.ACTIVE),
                is_occupied=False,
            )
            session.add(shelf)
            await session.flush()
            shelf_ids.append(shelf.id)

        await session.commit()
        return {
            "warehouse_id": warehouse.id,
            "rack_id": rack.id,
            "rack_code": rack.code,
            "shelf_ids": shelf_ids,
        }

async def create_warehouse_with_racks(racks: list[dict]) -> dict:
    
    async with async_session_maker() as session:
        warehouse = Warehouse(name=unique("Склад"), total_area=Decimal("100.00"))
        session.add(warehouse)
        await session.flush()

        result: dict = {"warehouse_id": warehouse.id, "racks": []}
        for rack_spec in racks:
            code = rack_spec.get("code") or unique("R")
            shelf_specs = rack_spec.get("shelves") or []
            rack = Rack(
                warehouse_id=warehouse.id,
                code=code,
                x=Decimal("1.0"),
                y=Decimal("1.0"),
                width=Decimal("1.0"),
                length=Decimal("2.0"),
                rotation_angle=Decimal("0"),
                shelves_count=len(shelf_specs),
            )
            session.add(rack)
            await session.flush()

            shelf_ids: list[int] = []
            for index, spec in enumerate(shelf_specs, start=1):
                shelf = Shelf(
                    rack_id=rack.id,
                    code=spec.get("code") or f"{code}-{index}",
                    qr=unique("QR"),
                    width=Decimal(str(spec.get("width", 2))),
                    length=Decimal(str(spec.get("length", 1))),
                    height=Decimal(str(spec.get("height", 1))),
                    max_weight=Decimal(str(spec.get("max_weight", 500))),
                    status=spec.get("status", ShelfStatus.ACTIVE),
                    is_occupied=False,
                )
                session.add(shelf)
                await session.flush()
                shelf_ids.append(shelf.id)

            result["racks"].append(
                {"rack_id": rack.id, "rack_code": code, "shelf_ids": shelf_ids}
            )

        await session.commit()
        return result
