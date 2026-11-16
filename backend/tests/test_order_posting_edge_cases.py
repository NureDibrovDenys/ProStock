"""Проведення накладних: граничні випадки залишків і захист проведених накладних.

Доповнює test_outbound_orders.py (базове проведення, нестача, точний залишок,
повторне проведення, видалення проведеної) випадками, яких там немає.
"""
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
STOCK = f"{API}/stock"

SHELVES = [{"code": "A-1", "width": "2", "length": "1", "height": "1", "max_weight": "500"}]


async def _fixture(client: AsyncClient, token: str) -> dict:
    warehouse = await create_warehouse_with_shelves(SHELVES)
    category_id = await create_category(client, token)
    product_id = await create_product(
        client, token, category_id, name="Борошно, 1 кг", width=0.2, length=0.2, height=0.1, weight=1.0
    )
    return {
        **warehouse,
        "product_id": product_id,
        "supplier_id": await create_supplier(client, token),
        "recipient_id": await create_recipient(client, token),
    }


def _inbound_body(fixture: dict, quantity: str, **extra) -> dict:
    return {
        "supplier_id": fixture["supplier_id"],
        "warehouse_id": fixture["warehouse_id"],
        "invoice_number": unique("INV"),
        "expected_delivery_date": "2026-12-01T00:00:00Z",
        "items": [{"product_id": fixture["product_id"], "quantity": quantity, "package_type": "box"}],
        **extra,
    }


def _outbound_body(fixture: dict, items: list[tuple[str, str]] | str, **extra) -> dict:
    lines = [(items, "box")] if isinstance(items, str) else items
    return {
        "recipient_id": fixture["recipient_id"],
        "warehouse_id": fixture["warehouse_id"],
        "planned_shipment_date": "2026-12-02T00:00:00Z",
        "items": [
            {"product_id": fixture["product_id"], "quantity": quantity, "package_type": package}
            for quantity, package in lines
        ],
        **extra,
    }


async def _available(client: AsyncClient, token: str, fixture: dict) -> Decimal:
    response = await client.get(
        STOCK,
        headers=auth(token),
        params={"warehouse_id": fixture["warehouse_id"], "product_ids": fixture["product_id"]},
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    return Decimal(rows[0]["available"]) if rows else Decimal("0")


async def _posted_inbound(client: AsyncClient, token: str, fixture: dict, quantity: str) -> dict:
    created = await client.post(INBOUND, headers=auth(token), json=_inbound_body(fixture, quantity))
    assert created.status_code == 201, created.text
    order = created.json()
    posted = await client.post(f"{INBOUND}/{order['inbound_order_id']}/post", headers=auth(token))
    assert posted.status_code == 200, posted.text
    return order


async def _posted_outbound(client: AsyncClient, token: str, fixture: dict, quantity: str) -> dict:
    created = await client.post(OUTBOUND, headers=auth(token), json=_outbound_body(fixture, quantity))
    assert created.status_code == 201, created.text
    order = created.json()
    posted = await client.post(f"{OUTBOUND}/{order['outbound_order_id']}/post", headers=auth(token))
    assert posted.status_code == 200, posted.text
    return order


# ── Проведену накладну не можна «перепровести» ──────────────────────────────


async def test_posted_inbound_cannot_be_reverted_to_draft_and_posted_again(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    order = await _posted_inbound(client, token, fixture, "10")
    url = f"{INBOUND}/{order['inbound_order_id']}"

    reverted = await client.patch(url, headers=auth(token), json={"order_status": "draft"})
    assert reverted.status_code == 409, reverted.text

    reposted = await client.post(f"{url}/post", headers=auth(token))
    assert reposted.status_code == 409, reposted.text
    assert await _available(client, token, fixture) == Decimal("10")


async def test_posted_outbound_cannot_be_reverted_to_draft_and_posted_again(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _posted_inbound(client, token, fixture, "10")
    order = await _posted_outbound(client, token, fixture, "4")
    url = f"{OUTBOUND}/{order['outbound_order_id']}"

    reverted = await client.patch(url, headers=auth(token), json={"order_status": "draft"})
    assert reverted.status_code == 409, reverted.text

    reposted = await client.post(f"{url}/post", headers=auth(token))
    assert reposted.status_code == 409, reposted.text
    assert await _available(client, token, fixture) == Decimal("6")


async def test_posted_inbound_items_cannot_be_edited(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    order = await _posted_inbound(client, token, fixture, "10")

    response = await client.patch(
        f"{INBOUND}/{order['inbound_order_id']}",
        headers=auth(token),
        json={"items": [{"product_id": fixture["product_id"], "quantity": "999", "package_type": "box"}]},
    )
    assert response.status_code == 409, response.text

    current = await client.get(f"{INBOUND}/{order['inbound_order_id']}", headers=auth(token))
    assert Decimal(current.json()["items"][0]["quantity"]) == Decimal("10")
    assert await _available(client, token, fixture) == Decimal("10")


async def test_draft_inbound_items_can_be_edited(client: AsyncClient):
    """Заміна позицій чернетки через PATCH (раніше падала з 500)."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    created = await client.post(INBOUND, headers=auth(token), json=_inbound_body(fixture, "10"))
    url = f"{INBOUND}/{created.json()['inbound_order_id']}"

    response = await client.patch(
        url,
        headers=auth(token),
        json={"items": [{"product_id": fixture["product_id"], "quantity": "25", "package_type": "pallet"}]},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert Decimal(items[0]["quantity"]) == Decimal("25")
    assert items[0]["package_type"] == "pallet"

    posted = await client.post(f"{url}/post", headers=auth(token))
    assert posted.status_code == 200, posted.text
    assert await _available(client, token, fixture) == Decimal("25")


async def test_posted_outbound_warehouse_cannot_be_changed(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    other = await create_warehouse_with_shelves(SHELVES)
    await _posted_inbound(client, token, fixture, "10")
    order = await _posted_outbound(client, token, fixture, "3")

    response = await client.patch(
        f"{OUTBOUND}/{order['outbound_order_id']}",
        headers=auth(token),
        json={"warehouse_id": other["warehouse_id"]},
    )
    assert response.status_code == 409, response.text


async def test_order_cannot_be_completed_without_posting(client: AsyncClient):
    """Статус «Завершено» ставить лише проведення, інакше накладна «закрита» без руху товару."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)

    created_completed = await client.post(
        INBOUND, headers=auth(token), json=_inbound_body(fixture, "10", order_status="completed")
    )
    assert created_completed.status_code == 422, created_completed.text

    draft = await client.post(INBOUND, headers=auth(token), json=_inbound_body(fixture, "10"))
    assert draft.status_code == 201, draft.text
    patched = await client.patch(
        f"{INBOUND}/{draft.json()['inbound_order_id']}", headers=auth(token), json={"order_status": "completed"}
    )
    assert patched.status_code == 422, patched.text

    outbound = await client.post(
        OUTBOUND, headers=auth(token), json=_outbound_body(fixture, "1", order_status="completed")
    )
    assert outbound.status_code == 422, outbound.text
    assert await _available(client, token, fixture) == Decimal("0")


async def test_canceled_order_cannot_be_posted(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    draft = await client.post(INBOUND, headers=auth(token), json=_inbound_body(fixture, "10"))
    url = f"{INBOUND}/{draft.json()['inbound_order_id']}"

    canceled = await client.patch(url, headers=auth(token), json={"order_status": "canceled"})
    assert canceled.status_code == 200, canceled.text

    response = await client.post(f"{url}/post", headers=auth(token))
    assert response.status_code == 409, response.text
    assert await _available(client, token, fixture) == Decimal("0")


# ── Граничні випадки залишків ───────────────────────────────────────────────


async def test_two_lines_of_one_product_are_checked_together(client: AsyncClient):
    """Кожен рядок окремо вміщається в залишок, а разом — ні: проведення має відмовити повністю."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _posted_inbound(client, token, fixture, "10")

    created = await client.post(
        OUTBOUND, headers=auth(token), json=_outbound_body(fixture, [("6", "box"), ("6", "pallet")])
    )
    assert created.status_code == 201, created.text

    response = await client.post(f"{OUTBOUND}/{created.json()['outbound_order_id']}/post", headers=auth(token))
    assert response.status_code == 409, response.text
    shortage = response.json()["detail"]["shortages"][0]
    assert Decimal(shortage["requested"]) == Decimal("12")
    assert Decimal(shortage["available"]) == Decimal("10")
    assert await _available(client, token, fixture) == Decimal("10")


async def test_fractional_quantities_down_to_one_hundredth(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _posted_inbound(client, token, fixture, "1.25")
    await _posted_outbound(client, token, fixture, "1.24")
    assert await _available(client, token, fixture) == Decimal("0.01")

    too_precise = await client.post(OUTBOUND, headers=auth(token), json=_outbound_body(fixture, "0.001"))
    assert too_precise.status_code == 422, too_precise.text
    negative = await client.post(OUTBOUND, headers=auth(token), json=_outbound_body(fixture, "-1"))
    assert negative.status_code == 422, negative.text


async def test_outbound_takes_stock_only_from_its_warehouse(client: AsyncClient):
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    other = {**fixture, **(await create_warehouse_with_shelves(SHELVES))}
    await _posted_inbound(client, token, fixture, "5")
    await _posted_inbound(client, token, other, "50")

    # На складі накладної лише 5, хоча загалом по системі 55
    created = await client.post(OUTBOUND, headers=auth(token), json=_outbound_body(fixture, "6"))
    response = await client.post(f"{OUTBOUND}/{created.json()['outbound_order_id']}/post", headers=auth(token))
    assert response.status_code == 409, response.text

    await _posted_outbound(client, token, fixture, "5")
    assert await _available(client, token, fixture) == Decimal("0")
    assert await _available(client, token, other) == Decimal("50")


async def test_stock_returns_to_zero_after_full_cycle(client: AsyncClient):
    """Прихід → повна відвантаження → ще одна відвантаження відхиляється."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    await _posted_inbound(client, token, fixture, "7")
    await _posted_outbound(client, token, fixture, "7")
    assert await _available(client, token, fixture) == Decimal("0")

    created = await client.post(OUTBOUND, headers=auth(token), json=_outbound_body(fixture, "0.01"))
    response = await client.post(f"{OUTBOUND}/{created.json()['outbound_order_id']}/post", headers=auth(token))
    assert response.status_code == 409, response.text


async def test_inbound_orders_list_filters_by_status(client: AsyncClient):
    """GET /inbound-orders (раніше 500 на будь-який запит через помилку в count-запиті)."""
    token = await login(client, ADMIN)
    fixture = await _fixture(client, token)
    order = await _posted_inbound(client, token, fixture, "3")
    draft = await client.post(INBOUND, headers=auth(token), json=_inbound_body(fixture, "1"))

    params = {"warehouse_id": fixture["warehouse_id"]}
    response = await client.get(INBOUND, headers=auth(token), params=params)
    assert response.status_code == 200, response.text
    ids = {o["inbound_order_id"] for o in response.json()}
    assert ids == {order["inbound_order_id"], draft.json()["inbound_order_id"]}

    completed = await client.get(INBOUND, headers=auth(token), params={**params, "order_status": "completed"})
    assert [o["inbound_order_id"] for o in completed.json()] == [order["inbound_order_id"]]


# ── Доступ до накладних чужого складу ───────────────────────────────────────


async def _manager_of(client: AsyncClient, admin_token: str, warehouse_id: int) -> str:
    email = f"{unique('mgr')}@prostock.com"
    created = await client.post(
        f"{API}/users",
        headers=auth(admin_token),
        json={
            "first_name": "Тест",
            "last_name": "Менеджер",
            "user_email": email,
            "password": "Manager12345",
            "role": "warehouse_manager",
            "warehouse_id": warehouse_id,
        },
    )
    assert created.status_code == 201, created.text
    return await login(client, (email, "Manager12345"))


async def test_manager_cannot_create_or_post_orders_of_foreign_warehouse(client: AsyncClient):
    admin = await login(client, ADMIN)
    fixture = await _fixture(client, admin)
    own = await create_warehouse_with_shelves(SHELVES)
    manager = await _manager_of(client, admin, own["warehouse_id"])

    # Створити накладну на чужий склад
    response = await client.post(INBOUND, headers=auth(manager), json=_inbound_body(fixture, "10"))
    assert response.status_code == 403, response.text

    # Провести чужу накладну, створену адміністратором
    foreign = await client.post(INBOUND, headers=auth(admin), json=_inbound_body(fixture, "10"))
    order_id = foreign.json()["inbound_order_id"]
    response = await client.post(f"{INBOUND}/{order_id}/post", headers=auth(manager))
    assert response.status_code == 403, response.text
    assert await _available(client, admin, fixture) == Decimal("0")

    # Перенести чужу накладну на свій склад теж не можна
    response = await client.patch(
        f"{INBOUND}/{order_id}", headers=auth(manager), json={"warehouse_id": own["warehouse_id"]}
    )
    assert response.status_code == 403, response.text

    # У списках чужих накладних не видно, а залишки чужого складу закриті
    listed = await client.get(f"{API}/orders", headers=auth(manager))
    assert listed.status_code == 200, listed.text
    assert order_id not in {o["order_id"] for o in listed.json()["items"] if o["order_type"] == "inbound"}
    stock = await client.get(STOCK, headers=auth(manager), params={"warehouse_id": fixture["warehouse_id"]})
    assert stock.status_code == 403, stock.text
