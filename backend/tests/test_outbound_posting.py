
from __future__ import annotations

import asyncio
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
    invoice_number: str | None = None,
) -> dict:
    payload: dict = {
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
    }
    if invoice_number is not None:
        payload["invoice_number"] = invoice_number
    response = await client.post(OUTBOUND, headers=auth(token), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _post(client: AsyncClient, token: str, order_id: int):
    return await client.post(f"{OUTBOUND}/{order_id}/post", headers=auth(token))


async def _stock_level(client: AsyncClient, token: str, fixture: dict) -> Decimal:
    response = await client.get(
        STOCK,
        headers=auth(token),
        params={
            "warehouse_id": fixture["warehouse_id"],
            "product_ids": fixture["product_id"],
        },
    )
    assert response.status_code == 200, response.text
    levels = response.json()
    if not levels:
        return Decimal("0")
    return Decimal(levels[0]["available"])


async def _stock_inbound(client: AsyncClient, token: str, fixture: dict, quantity: str) -> None:
    inbound = await _create_inbound(client, token, fixture, quantity=quantity)
    response = await client.post(
        f"{INBOUND}/{inbound['inbound_order_id']}/post", headers=auth(token)
    )
    assert response.status_code == 200, response.text


async def test_update_cannot_remove_all_lines(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    order = await _create_outbound(client, token, fixture, quantity="5")
    response = await client.patch(
        f"{OUTBOUND}/{order['outbound_order_id']}",
        headers=auth(token),
        json={"items": []},
    )
    assert response.status_code == 422, response.text

    fetched = await client.get(
        f"{OUTBOUND}/{order['outbound_order_id']}", headers=auth(token)
    )
    assert len(fetched.json()["items"]) == 1


async def test_completed_order_cannot_be_edited(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _stock_inbound(client, token, fixture, quantity="100")

    order = await _create_outbound(client, token, fixture, quantity="10")
    posted = await _post(client, token, order["outbound_order_id"])
    assert posted.status_code == 200, posted.text
    assert posted.json()["order_status"] == "completed"

    response = await client.patch(
        f"{OUTBOUND}/{order['outbound_order_id']}",
        headers=auth(token),
        json={"planned_shipment_date": "2026-12-20T00:00:00Z"},
    )
    assert response.status_code == 409, response.text
    assert "проведен" in response.json()["detail"].lower()


async def test_posted_order_cannot_be_reopened_and_posted_again(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _stock_inbound(client, token, fixture, quantity="100")

    order = await _create_outbound(client, token, fixture, quantity="10")
    assert await _stock_level(client, token, fixture) == Decimal("100")

    posted = await _post(client, token, order["outbound_order_id"])
    assert posted.status_code == 200, posted.text
    assert await _stock_level(client, token, fixture) == Decimal("90")

    reopened = await client.patch(
        f"{OUTBOUND}/{order['outbound_order_id']}",
        headers=auth(token),
        json={"order_status": "draft"},
    )
    assert reopened.status_code == 409, reopened.text

    again = await _post(client, token, order["outbound_order_id"])
    assert again.status_code == 409, again.text
    assert "чернет" in again.json()["detail"].lower()

    assert await _stock_level(client, token, fixture) == Decimal("90")


async def test_order_cannot_be_created_as_completed_without_posting(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _stock_inbound(client, token, fixture, quantity="100")

    response = await client.post(
        OUTBOUND,
        headers=auth(token),
        json={
            "recipient_id": fixture["recipient_id"],
            "warehouse_id": fixture["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "order_status": "completed",
            "items": [
                {
                    "product_id": fixture["product_id"],
                    "quantity": "10",
                    "package_type": "box",
                }
            ],
        },
    )
    assert response.status_code == 422, response.text
    assert await _stock_level(client, token, fixture) == Decimal("100")


async def test_parallel_posts_of_same_order_write_off_once(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _stock_inbound(client, token, fixture, quantity="100")

    order = await _create_outbound(client, token, fixture, quantity="30")

    first, second = await asyncio.gather(
        _post(client, token, order["outbound_order_id"]),
        _post(client, token, order["outbound_order_id"]),
        return_exceptions=True,
    )

    statuses = sorted(
        response.status_code
        for response in (first, second)
        if not isinstance(response, Exception)
    )
    assert statuses == [200, 409], (statuses, first, second)
    assert await _stock_level(client, token, fixture) == Decimal("70")


async def test_parallel_posts_cannot_oversell_stock(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _stock_inbound(client, token, fixture, quantity="100")

    first_order = await _create_outbound(client, token, fixture, quantity="60")
    second_order = await _create_outbound(client, token, fixture, quantity="60")

    first, second = await asyncio.gather(
        _post(client, token, first_order["outbound_order_id"]),
        _post(client, token, second_order["outbound_order_id"]),
        return_exceptions=True,
    )

    statuses = sorted(
        response.status_code
        for response in (first, second)
        if not isinstance(response, Exception)
    )
    assert statuses == [200, 409], (statuses, first, second)
    assert await _stock_level(client, token, fixture) == Decimal("40")
