"""Довідники постачальників і одержувачів: CRUD і валідація полів.

Доповнює test_counterparties.py (повний цикл CRUD, базові некоректні значення,
дубль ЄДРПОУ постачальника, права доступу) граничними значеннями та зв'язком
довідників із накладними.
"""
from __future__ import annotations

import uuid

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

SUPPLIERS = f"{API}/suppliers"
RECIPIENTS = f"{API}/recipients"


def _digits(length: int) -> str:
    """Унікальний набір цифр потрібної довжини (ЄДРПОУ постачальника унікальний у БД)."""
    return str(uuid.uuid4().int)[:length]


# ── Видалення контрагента, на якого посилаються накладні ───────────────────


async def test_supplier_with_inbound_orders_cannot_be_deleted(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse_with_shelves()
    product_id = await create_product(client, token, await create_category(client, token))
    supplier_id = await create_supplier(client, token)
    order = await client.post(
        f"{API}/inbound-orders",
        headers=auth(token),
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse["warehouse_id"],
            "invoice_number": unique("INV"),
            "expected_delivery_date": "2026-12-01T00:00:00Z",
            "items": [{"product_id": product_id, "quantity": "1", "package_type": "box"}],
        },
    )
    assert order.status_code == 201, order.text

    response = await client.delete(f"{SUPPLIERS}/{supplier_id}", headers=auth(token))
    assert response.status_code == 409, response.text
    assert (await client.get(f"{SUPPLIERS}/{supplier_id}", headers=auth(token))).status_code == 200

    # Замість видалення - архів
    archived = await client.patch(f"{SUPPLIERS}/{supplier_id}", headers=auth(token), json={"status": "inactive"})
    assert archived.status_code == 200, archived.text


async def test_recipient_with_outbound_orders_cannot_be_deleted(client: AsyncClient):
    token = await login(client, ADMIN)
    warehouse = await create_warehouse_with_shelves()
    product_id = await create_product(client, token, await create_category(client, token))
    recipient_id = await create_recipient(client, token)
    order = await client.post(
        f"{API}/outbound-orders",
        headers=auth(token),
        json={
            "recipient_id": recipient_id,
            "warehouse_id": warehouse["warehouse_id"],
            "planned_shipment_date": "2026-12-02T00:00:00Z",
            "items": [{"product_id": product_id, "quantity": "1", "package_type": "box"}],
        },
    )
    assert order.status_code == 201, order.text

    response = await client.delete(f"{RECIPIENTS}/{recipient_id}", headers=auth(token))
    assert response.status_code == 409, response.text
    assert (await client.get(f"{RECIPIENTS}/{recipient_id}", headers=auth(token))).status_code == 200


async def test_only_active_counterparties_can_be_used_in_new_orders(client: AsyncClient):
    """Форма накладної пропонує лише активних; бекенд має відхиляти й прямий запит."""
    token = await login(client, ADMIN)
    warehouse = await create_warehouse_with_shelves()
    product_id = await create_product(client, token, await create_category(client, token))
    item = [{"product_id": product_id, "quantity": "1", "package_type": "box"}]

    for status_value in ("inactive", "blocked"):
        supplier_id = await create_supplier(client, token, status=status_value)
        response = await client.post(
            f"{API}/inbound-orders",
            headers=auth(token),
            json={
                "supplier_id": supplier_id,
                "warehouse_id": warehouse["warehouse_id"],
                "invoice_number": unique("INV"),
                "expected_delivery_date": "2026-12-01T00:00:00Z",
                "items": item,
            },
        )
        assert response.status_code == 422, (status_value, response.text)

        recipient_id = await create_recipient(client, token, status=status_value)
        response = await client.post(
            f"{API}/outbound-orders",
            headers=auth(token),
            json={
                "recipient_id": recipient_id,
                "warehouse_id": warehouse["warehouse_id"],
                "planned_shipment_date": "2026-12-02T00:00:00Z",
                "items": item,
            },
        )
        assert response.status_code == 422, (status_value, response.text)


# ── Валідація полів ─────────────────────────────────────────────────────────


async def test_required_fields_cannot_be_cleared_with_null(client: AsyncClient):
    token = await login(client, ADMIN)
    supplier_id = await create_supplier(client, token)
    recipient_id = await create_recipient(client, token)

    response = await client.patch(f"{SUPPLIERS}/{supplier_id}", headers=auth(token), json={"company_name": None})
    assert response.status_code == 422, response.text
    for field in ("company_name", "address"):
        response = await client.patch(f"{RECIPIENTS}/{recipient_id}", headers=auth(token), json={field: None})
        assert response.status_code == 422, (field, response.text)

    # Необов'язкові поля null очищує
    cleared = await client.patch(
        f"{SUPPLIERS}/{supplier_id}", headers=auth(token), json={"phone_number": None, "email": None}
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["phone_number"] is None
    assert cleared.json()["email"] is None


async def test_text_fields_are_normalized(client: AsyncClient):
    token = await login(client, ADMIN)
    name = unique("ТОВ")
    response = await client.post(
        SUPPLIERS,
        headers=auth(token),
        json={
            "company_name": f"   {name}    «Зерно»  ",
            "contact_person": "  Іван    Іванович ",
            "email": f"  {unique('Sales')}@Example.COM ",
            "address": "   ",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["company_name"] == f"{name} «Зерно»"
    assert body["contact_person"] == "Іван Іванович"
    assert body["email"] == body["email"].lower() and body["email"].startswith("sales")
    assert body["address"] is None


async def test_field_length_boundaries(client: AsyncClient):
    token = await login(client, ADMIN)

    def name(length: int) -> str:
        return (unique("Н") + "я" * length)[:length]

    assert (await client.post(SUPPLIERS, headers=auth(token), json={"company_name": name(255)})).status_code == 201
    assert (await client.post(SUPPLIERS, headers=auth(token), json={"company_name": name(256)})).status_code == 422

    base = {"company_name": unique("ТОВ")}
    assert (await client.post(SUPPLIERS, headers=auth(token), json={**base, "contact_person": "я" * 150})).status_code == 201
    base = {"company_name": unique("ТОВ")}
    assert (await client.post(SUPPLIERS, headers=auth(token), json={**base, "contact_person": "я" * 151})).status_code == 422

    recipient = {"company_name": unique("ТОВ"), "address": "a" * 1000}
    assert (await client.post(RECIPIENTS, headers=auth(token), json=recipient)).status_code == 201
    recipient = {"company_name": unique("ТОВ"), "address": "a" * 1001}
    assert (await client.post(RECIPIENTS, headers=auth(token), json=recipient)).status_code == 422


async def test_tax_id_and_phone_boundaries(client: AsyncClient):
    token = await login(client, ADMIN)

    async def supplier(**fields) -> int:
        response = await client.post(SUPPLIERS, headers=auth(token), json={"company_name": unique("ТОВ"), **fields})
        return response.status_code

    assert await supplier(tax_id=_digits(8)) == 201  # ЄДРПОУ
    assert await supplier(tax_id=_digits(10)) == 201  # ІПН
    for bad in ("1234567", "123456789", "12345678901", "1234567a"):
        assert await supplier(tax_id=bad) == 422, bad

    assert await supplier(phone_number="1234567") == 201  # 7 цифр
    assert await supplier(phone_number="+380 (50) 123-45-67") == 201
    assert await supplier(phone_number="123456789012345") == 201  # 15 цифр
    for bad in ("123456", "1234567890123456", "+38050abc4567"):
        assert await supplier(phone_number=bad) == 422, bad


async def test_recipients_may_share_tax_id(client: AsyncClient):
    """Філії однієї мережі мають спільний ЄДРПОУ - для одержувачів дубль дозволено."""
    token = await login(client, ADMIN)
    tax_id = _digits(8)
    for _ in range(2):
        response = await client.post(
            RECIPIENTS,
            headers=auth(token),
            json={"company_name": unique("Філія"), "address": "м. Київ", "tax_id": tax_id},
        )
        assert response.status_code == 201, response.text


async def test_tax_id_can_be_kept_on_update(client: AsyncClient):
    """PATCH із тим самим ЄДРПОУ не повинен вважатися дублем самого себе."""
    token = await login(client, ADMIN)
    tax_id = _digits(8)
    supplier_id = await create_supplier(client, token, tax_id=tax_id)

    response = await client.patch(
        f"{SUPPLIERS}/{supplier_id}", headers=auth(token), json={"tax_id": tax_id, "contact_person": "Нова особа"}
    )
    assert response.status_code == 200, response.text


# ── Пошук, фільтр, пагінація, неіснуючі записи ──────────────────────────────


async def test_status_filter_search_and_pagination(client: AsyncClient):
    token = await login(client, ADMIN)
    marker = unique("Фільтр")
    for status_value in ("active", "active", "blocked"):
        await create_supplier(client, token, company_name=f"{marker} {unique('')}", status=status_value)

    found = await client.get(SUPPLIERS, headers=auth(token), params={"search": marker})
    assert found.json()["total"] == 3

    blocked = await client.get(SUPPLIERS, headers=auth(token), params={"search": marker, "status": "blocked"})
    assert blocked.json()["total"] == 1
    assert blocked.json()["items"][0]["status"] == "blocked"

    page = await client.get(SUPPLIERS, headers=auth(token), params={"search": marker, "page_size": 2, "page": 2})
    assert page.status_code == 200, page.text
    assert len(page.json()["items"]) == 1
    assert page.json()["pages"] == 2

    for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 201}, {"status": "deleted"}):
        assert (await client.get(SUPPLIERS, headers=auth(token), params=bad)).status_code == 422, bad


async def test_missing_counterparty_returns_404(client: AsyncClient):
    token = await login(client, ADMIN)
    for url in (f"{SUPPLIERS}/999999", f"{RECIPIENTS}/999999"):
        assert (await client.get(url, headers=auth(token))).status_code == 404
        assert (await client.patch(url, headers=auth(token), json={"contact_person": "X"})).status_code == 404
        assert (await client.delete(url, headers=auth(token))).status_code == 404
