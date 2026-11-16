
from __future__ import annotations

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

SHELVES = [
    {"code": "A-1", "width": "2", "length": "1", "height": "1", "max_weight": "500"},
]


async def _fixture(client: AsyncClient, token: str) -> dict:
    
    warehouse = await create_warehouse_with_shelves(SHELVES)
    category_id = await create_category(client, token)
    product_id = await create_product(client, token, category_id)
    supplier_id = await create_supplier(client, token)
    recipient_id = await create_recipient(client, token)
    return {
        **warehouse,
        "category_id": category_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "recipient_id": recipient_id,
    }


async def test_create_duplicate_invoice_number_returns_400(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    invoice_number = unique("ДУБЛЬ")

    first = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "invoice_number": invoice_number,
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": "5",
                    "package_type": "box",
                }
            ],
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["invoice_number"] == invoice_number

    second = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "invoice_number": invoice_number,
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": "5",
                    "package_type": "box",
                }
            ],
        },
    )
    assert second.status_code == 400, second.text
    assert "already exists" in second.json()["detail"]


async def test_inbound_orders_list_endpoint_works(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    created = await client.post(
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
                    "quantity": "10",
                    "package_type": "box",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text

    listing = await client.get(INBOUND, headers=auth(token))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert created.json()["inbound_order_id"] in {
        item["inbound_order_id"] for item in body
    }

    filtered = await client.get(
        INBOUND,
        headers=auth(token),
        params={
            "warehouse_id": fixture["warehouse_id"],
            "order_status": "draft",
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()

    searched = await client.get(
        INBOUND,
        headers=auth(token),
        params={"search": created.json()["invoice_number"]},
    )
    assert searched.status_code == 200, searched.text
    assert len(searched.json()) == 1
