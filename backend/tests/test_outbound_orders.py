
from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.utils import (
    ADMIN,
    API,
    auth,
    create_category,
    create_product,
    create_recipient,
    create_supplier,
    create_warehouse_with_shelves,
    login,
    unique,
)

INBOUND = f"{API}/inbound-orders"
OUTBOUND = f"{API}/outbound-orders"
ORDERS = f"{API}/orders"
STOCK = f"{API}/stock"

SHELVES = [
    {"code": "A-1", "width": "2", "length": "1", "height": "1", "max_weight": "500"},
    {"code": "A-2", "width": "2", "length": "1", "height": "1", "max_weight": "500"},
]

async def _fixture(client: AsyncClient, token: str) -> dict:
    
    warehouse = await create_warehouse_with_shelves(SHELVES)
    category_id = await create_category(client, token)
    product_id = await create_product(
        client,
        token,
        category_id,
        name="Цукор, 1 кг",
        width=0.2,
        length=0.2,
        height=0.1,
        weight=1.0,
    )
    supplier_id = await create_supplier(client, token)
    recipient_id = await create_recipient(client, token)
    return {
        **warehouse,
        "category_id": category_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "recipient_id": recipient_id,
    }

async def _create_inbound(
    client: AsyncClient,
    token: str,
    fixture: dict,
    quantity: str = "100",
    invoice_number: str | None = None,
) -> dict:
    response = await client.post(
        INBOUND,
        headers=auth(token),
        json={
            "supplier_id": fixture["supplier_id"],
            "warehouse_id": fixture["warehouse_id"],
            "invoice_number": invoice_number or unique("INV"),
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
    return response.json()

async def _create_outbound(
    client: AsyncClient,
    token: str,
    fixture: dict,
    quantity: str = "10",
) -> dict:
    response = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
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
    return response.json()

async def test_outbound_order_crud(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    created = await _create_outbound(client, token, fixture, quantity="5")
    order_id = created["outbound_order_id"]
    assert created["recipient_id"] == fixture["recipient_id"]
    assert created["warehouse_id"] == fixture["warehouse_id"]
    assert created["order_status"] == "draft"
    assert created["invoice_number"] == f"ВН-{order_id:06d}"
    assert created["items"][0]["quantity"] == "5.00"

    fetched = await client.get(f"{OUTBOUND}/{order_id}", headers=auth(token))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["outbound_order_id"] == order_id

    listing = await client.get(OUTBOUND, headers=auth(token))
    assert listing.status_code == 200, listing.text
    assert order_id in {item["outbound_order_id"] for item in listing.json()}

    patched = await client.patch(
        f"{OUTBOUND}/{order_id}",
        headers=auth(token),
        json={
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": "7",
                    "package_type": "pallet",
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert len(patched.json()["items"]) == 1
    assert patched.json()["items"][0]["quantity"] == "7.00"
    assert patched.json()["items"][0]["package_type"] == "pallet"

    deleted = await client.delete(f"{OUTBOUND}/{order_id}", headers=auth(token))
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"{OUTBOUND}/{order_id}", headers=auth(token))).status_code == 404

async def test_outbound_order_validation(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    response = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": 999999,
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": "1",
                    "package_type": "box",
                }
            ],
        },
    )
    assert response.status_code == 404, response.text

    response = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "items": [
                {"product_id": 999999, "quantity": "1", "package_type": "box"}
            ],
        },
    )
    assert response.status_code == 404, response.text

    response = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "items": [],
        },
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "items": [
                {"product_id": fixture["product_id"], "quantity": "0", "package_type": "box"}
            ],
        },
    )
    assert response.status_code == 422, response.text

    order = await _create_outbound(client, token, fixture)
    response = await client.patch(
        f"{OUTBOUND}/{order['outbound_order_id']}", headers=auth(token), json={}
    )
    assert response.status_code == 422, response.text

async def test_outbound_order_requires_manager_role(client: AsyncClient):
    
    from tests.utils import WORKER

    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    worker_token = await login(client, WORKER)
    response = await client.post(
        OUTBOUND,
        headers=auth(worker_token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": "1",
                    "package_type": "box",
                }
            ],
        },
    )
    assert response.status_code == 403, response.text

async def test_stock_endpoint_reports_available_quantity(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="100")
    posted = await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    assert posted.status_code == 200, posted.text

    response = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    assert response.status_code == 200, response.text
    levels = response.json()
    assert len(levels) == 1
    assert Decimal(levels[0]["available"]) == Decimal("100")
    assert levels[0]["product_id"] == fixture["product_id"]

async def test_outbound_availability_check(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="40")
    await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )

    order = await _create_outbound(client, token, fixture, quantity="15")
    response = await client.get(
        f"{OUTBOUND}/{order['outbound_order_id']}/availability", headers=auth(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fits"] is True
    assert body["shortages"] == []

async def test_post_inbound_places_stock_on_shelves(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="100")
    response = await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_status"] == "completed"
    assert body["order_type"] == "inbound"

    fetched = await client.get(
        f"{INBOUND}/{inbound['inbound_order_id']}", headers=auth(token)
    )
    assert fetched.json()["order_status"] == "completed"

    shelves = await client.get(
        f"{API}/warehouses/{fixture['warehouse_id']}/racks/{fixture['rack_code']}/shelves",
        headers=auth(token),
    )
    assert shelves.status_code == 200, shelves.text
    total_used = sum(
        Decimal(str(shelf["used_volume_m3"])) for shelf in shelves.json()
    )
    assert total_used == Decimal("0.4")

async def test_post_outbound_decreases_stock(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="100")
    await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )

    order = await _create_outbound(client, token, fixture, quantity="30")
    response = await client.post(
        f"{OUTBOUND}/{order['outbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 200, response.text
    assert response.json()["order_status"] == "completed"

    levels = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    assert Decimal(levels.json()[0]["available"]) == Decimal("70")

async def test_post_outbound_without_stock_is_rejected(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    order = await _create_outbound(client, token, fixture, quantity="5")
    response = await client.post(
        f"{OUTBOUND}/{order['outbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "залиш" in detail["message"].lower()
    assert len(detail["shortages"]) == 1
    shortage = detail["shortages"][0]
    assert shortage["product_id"] == fixture["product_id"]
    assert Decimal(shortage["requested"]) == Decimal("5")
    assert Decimal(shortage["available"]) == Decimal("0")
    assert Decimal(shortage["shortage"]) == Decimal("5")

    fetched = await client.get(
        f"{OUTBOUND}/{order['outbound_order_id']}", headers=auth(token)
    )
    assert fetched.json()["order_status"] == "draft"

async def test_post_outbound_with_partial_stock_reports_shortage(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="10")
    await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )

    order = await _create_outbound(client, token, fixture, quantity="25")
    response = await client.post(
        f"{OUTBOUND}/{order['outbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 409, response.text
    shortage = response.json()["detail"]["shortages"][0]
    assert Decimal(shortage["available"]) == Decimal("10")
    assert Decimal(shortage["shortage"]) == Decimal("15")

    levels = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    assert Decimal(levels.json()[0]["available"]) == Decimal("10")

async def test_post_exactly_available_quantity_succeeds(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="12")
    await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )

    order = await _create_outbound(client, token, fixture, quantity="12")
    response = await client.post(
        f"{OUTBOUND}/{order['outbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 200, response.text

    levels = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    assert Decimal(levels.json()[0]["available"]) == Decimal("0")

async def test_post_cannot_be_repeated(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="10")
    first = await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    assert second.status_code == 409, second.text
    assert "чернет" in second.json()["detail"].lower()

async def test_posted_order_cannot_be_deleted(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="10")
    await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    response = await client.delete(
        f"{INBOUND}/{inbound['inbound_order_id']}", headers=auth(token)
    )
    assert response.status_code == 400, response.text

async def test_post_inbound_without_space_is_rejected(client: AsyncClient):
    
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="2000")
    response = await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["shortages"]
    assert Decimal(detail["shortages"][0]["unplaced"]) > 0

    levels = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    assert levels.json() == [] or Decimal(levels.json()[0]["available"]) == Decimal("0")

async def test_unified_orders_list_filters_by_type_and_status(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    inbound = await _create_inbound(client, token, fixture, quantity="10")
    outbound = await _create_outbound(client, token, fixture, quantity="5")

    everything = await client.get(ORDERS, headers=auth(token))
    assert everything.status_code == 200, everything.text
    body = everything.json()
    types = {item["order_type"] for item in body["items"]}
    assert {"inbound", "outbound"} <= types

    only_inbound = await client.get(
        ORDERS, headers=auth(token), params={"order_type": "inbound"}
    )
    assert only_inbound.status_code == 200, only_inbound.text
    assert {item["order_type"] for item in only_inbound.json()["items"]} == {"inbound"}
    assert inbound["inbound_order_id"] in {
        item["order_id"] for item in only_inbound.json()["items"]
    }

    only_outbound = await client.get(
        ORDERS, headers=auth(token), params={"order_type": "outbound"}
    )
    assert {item["order_type"] for item in only_outbound.json()["items"]} == {"outbound"}
    assert outbound["outbound_order_id"] in {
        item["order_id"] for item in only_outbound.json()["items"]
    }

    drafts = await client.get(
        ORDERS, headers=auth(token), params={"order_status": "draft"}
    )
    assert drafts.status_code == 200, drafts.text
    assert {item["order_status"] for item in drafts.json()["items"]} == {"draft"}
    assert inbound["inbound_order_id"] in {
        item["order_id"] for item in drafts.json()["items"]
    }

    completed = await client.get(
        ORDERS, headers=auth(token), params={"order_status": "completed"}
    )
    assert completed.status_code == 200, completed.text
    assert {item["order_status"] for item in completed.json()["items"]} <= {"completed"}
    assert inbound["inbound_order_id"] not in {
        item["order_id"] for item in completed.json()["items"]
    }

    search = await client.get(
        ORDERS, headers=auth(token), params={"search": "Одержувач"}
    )
    assert search.status_code == 200, search.text
    assert all(
        item["order_type"] == "outbound" for item in search.json()["items"]
    )

async def test_unified_orders_list_contains_counterparty_and_number(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    outbound = await _create_outbound(client, token, fixture, quantity="5")
    response = await client.get(ORDERS, headers=auth(token))
    assert response.status_code == 200, response.text

    item = next(
        entry
        for entry in response.json()["items"]
        if entry["order_id"] == outbound["outbound_order_id"]
    )
    assert item["order_type"] == "outbound"
    assert item["number"] == f"ВН-{outbound['outbound_order_id']:06d}"
    assert item["counterparty_id"] == fixture["recipient_id"]
    assert item["counterparty_name"]
    assert item["items_count"] == 1
    assert item["total_quantity"] == "5.00"
