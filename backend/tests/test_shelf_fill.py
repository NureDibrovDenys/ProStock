
from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from app.core.db import async_session_maker
from app.warehouses.services import fill_service
from tests.utils import (
    ADMIN,
    API,
    auth,
    create_category,
    create_product,
    create_supplier,
    create_warehouse_with_racks,
    create_warehouse_with_shelves,
    login,
    unique,
)

INBOUND = f"{API}/inbound-orders"

SHELF = {"width": "2", "length": "1", "height": "1", "max_weight": "500"}

PRODUCT = {
    "width": 0.5,
    "length": 0.5,
    "height": 0.2,
    "weight": 10.0,
    "unit_of_measure": "box",
}

async def _stock_in(client: AsyncClient, token: str, fixture: dict, quantity: str) -> None:
    
    response = await client.post(
        INBOUND,
        headers=auth(token),
        json={
            "supplier_id": fixture["supplier_id"],
            "warehouse_id": fixture["warehouse_id"],
            "invoice_number": unique("INV"),
            "expected_delivery_date": "2026-12-01T00:00:00Z",
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": quantity,
                    "package_type": "box",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    posted = await client.post(
        f"{INBOUND}/{response.json()['inbound_order_id']}/post",
        headers=auth(token),
    )
    assert posted.status_code == 200, posted.text

async def _fixture(client: AsyncClient, token: str, racks: list[dict]) -> dict:
    warehouse = await create_warehouse_with_racks(racks)
    category_id = await create_category(client, token)
    product_id = await create_product(
        client, token, category_id, name="Коробка", **PRODUCT
    )
    supplier_id = await create_supplier(client, token)
    return {
        **warehouse,
        "category_id": category_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
    }

async def test_empty_shelf_has_zero_fill(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse_with_shelves([dict(SHELF, code="S-1")])

    shelves = await client.get(
        f"{API}/warehouses/{warehouse['warehouse_id']}/racks/{warehouse['rack_code']}/shelves",
        headers=auth(token),
    )
    assert shelves.status_code == 200, shelves.text
    shelf = shelves.json()[0]
    assert shelf["volume_m3"] == 2.0
    assert shelf["used_volume_m3"] == 0.0
    assert shelf["volume_fill_percent"] == 0.0
    assert shelf["weight_fill_percent"] == 0.0
    assert shelf["free_volume_m3"] == 2.0
    assert shelf["items_count"] == 0

async def test_shelf_fill_after_incoming_stock(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}])

    await _stock_in(client, token, fixture, "10")

    shelves = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/racks/A/shelves",
        headers=auth(token),
    )
    assert shelves.status_code == 200, shelves.text
    shelf = shelves.json()[0]
    assert Decimal(str(shelf["used_volume_m3"])) == Decimal("0.5")
    assert Decimal(str(shelf["used_weight_kg"])) == Decimal("100")
    assert shelf["volume_fill_percent"] == 25.0
    assert shelf["weight_fill_percent"] == 20.0
    assert Decimal(str(shelf["free_volume_m3"])) == Decimal("1.5")
    assert shelf["items_count"] == 1

async def test_rack_fill_is_sum_of_its_shelves(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [
            {
                "code": "A",
                "shelves": [
                    dict(SHELF, code="A-1"),
                    dict(SHELF, code="A-2"),
                ],
            },
            {
                "code": "B",
                "shelves": [dict(SHELF, code="B-1")],
            },
        ],
    )

    await _stock_in(client, token, fixture, "20")

    rack = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/racks/A", headers=auth(token)
    )
    assert rack.status_code == 200, rack.text
    body = rack.json()

    shelves = {shelf["shelf_code"]: shelf for shelf in body["shelves"]}
    assert set(shelves) == {"A-1", "A-2"}

    shelf_volumes = sorted(
        Decimal(str(shelf["used_volume_m3"])) for shelf in shelves.values()
    )
    assert shelf_volumes == [Decimal("0"), Decimal("1")]

    assert Decimal(str(body["used_volume_m3"])) == sum(shelf_volumes)
    assert Decimal(str(body["total_volume_m3"])) == Decimal("4")
    assert Decimal(str(body["used_weight_kg"])) == Decimal("200")
    assert body["volume_fill_percent"] == 25.0
    assert body["weight_fill_percent"] == 20.0

async def test_rack_summary_endpoint_reports_fill(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [{"code": "A", "shelves": [dict(SHELF, code="A-1"), dict(SHELF, code="A-2")]}],
    )

    await _stock_in(client, token, fixture, "10")

    racks = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/racks", headers=auth(token)
    )
    assert racks.status_code == 200, racks.text
    summary = next(r for r in racks.json() if r["rack_code"] == "A")
    assert summary["shelves_count"] == 2
    assert summary["fill_percent"] == 12.5  # 0.5 м³ із 4 м³
    assert summary["volume_fill_percent"] == 12.5
    assert summary["weight_fill_percent"] == 10.0  # 100 кг із 1000 кг
    assert summary["shelves_used"] == 1
    assert summary["overloaded"] is False

async def test_warehouse_map_contains_rack_fill(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client, token, [{"code": "A", "shelves": [dict(SHELF, code="A-1")]}]
    )

    await _stock_in(client, token, fixture, "20")

    response = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/map", headers=auth(token)
    )
    assert response.status_code == 200, response.text
    racks = response.json()["racks"]
    assert racks, "на карті має бути стелаж"
    rack = racks[0]
    assert rack["rack_code"] == "A"
    assert rack["fill_percent"] == 50.0  # 1 м³ із 2 м³
    assert rack["volume_fill_percent"] == 50.0
    assert rack["weight_fill_percent"] == 40.0  # 200 кг із 500 кг
    assert Decimal(str(rack["used_volume_m3"])) == Decimal("1")
    assert Decimal(str(rack["total_volume_m3"])) == Decimal("2")

async def test_fill_service_reports_hierarchy(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [
            {
                "code": "A",
                "shelves": [dict(SHELF, code="A-1"), dict(SHELF, code="A-2")],
            },
            {"code": "B", "shelves": [dict(SHELF, code="B-1")]},
        ],
    )

    await _stock_in(client, token, fixture, "12")

    async with async_session_maker() as session:
        shelf_fills = await fill_service.get_shelf_fills(
            session, fixture["warehouse_id"]
        )
        rack_fills = await fill_service.get_rack_fills(session, fixture["warehouse_id"])
        capacity = await fill_service.get_warehouse_capacity(
            session, fixture["warehouse_id"]
        )

    assert len(shelf_fills) == 3
    assert len(rack_fills) == 2

    for rack_fill in rack_fills.values():
        shelf_sum = sum(
            (fill.used_volume_m3 for fill in rack_fill.shelves.values()), Decimal("0")
        )
        assert rack_fill.used_volume_m3 == shelf_sum
        assert rack_fill.total_volume_m3 == Decimal(
            str(len(rack_fill.shelves) * 2)
        )

    assert capacity["total_volume_m3"] == Decimal("6")
    assert Decimal(str(capacity["used_volume_m3"])) == Decimal("0.6")
    assert Decimal(str(capacity["free_volume_m3"])) == Decimal("5.4")

async def test_stock_is_spread_across_shelves(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [
            {
                "code": "A",
                "shelves": [
                    dict(SHELF, code="A-1"),
                    dict(SHELF, code="A-2"),
                ],
            }
        ],
    )

    await _stock_in(client, token, fixture, "60")

    shelves = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/racks/A/shelves",
        headers=auth(token),
    )
    body = shelves.json()
    used = [Decimal(str(shelf["used_volume_m3"])) for shelf in body]
    assert sum(used) == Decimal("3")
    assert max(used) <= Decimal("2")
    assert all(shelf["volume_fill_percent"] <= 100 for shelf in body)

async def test_inactive_shelf_is_not_used_for_placement(client: AsyncClient):
    
    from app.core.enums import ShelfStatus

    token = await login(client, ADMIN)
    fixture = await _fixture(
        client,
        token,
        [
            {
                "code": "A",
                "shelves": [
                    dict(SHELF, code="A-1", status=ShelfStatus.INACTIVE),
                    dict(SHELF, code="A-2"),
                ],
            }
        ],
    )

    await _stock_in(client, token, fixture, "10")

    shelves = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/racks/A/shelves",
        headers=auth(token),
    )
    by_code = {shelf["shelf_code"]: shelf for shelf in shelves.json()}
    assert Decimal(str(by_code["A-1"]["used_volume_m3"])) == Decimal("0")
    assert Decimal(str(by_code["A-2"]["used_volume_m3"])) == Decimal("0.5")
