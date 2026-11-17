
from __future__ import annotations

from httpx import AsyncClient

from tests.utils import (
    ADMIN,
    API,
    MANAGER,
    WORKER,
    auth,
    create_recipient,
    create_supplier,
    login,
    unique,
)

SUPPLIERS = f"{API}/suppliers"
RECIPIENTS = f"{API}/recipients"

async def test_supplier_crud_cycle(client: AsyncClient):
    token = await login(client, ADMIN)

    created = await client.post(
        SUPPLIERS,
        headers=auth(token),
        json={
            "company_name": "ТОВ «Агро-Трейд»",
            "tax_id": "12345678",
            "contact_person": "Марія Ковальчук",
            "phone_number": "+380 50 123 4567",
            "email": "Sales@agro-trade.example",
            "address": "м. Київ, вул. Хрещатик, 1",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    supplier_id = body["supplier_id"]
    assert body["company_name"] == "ТОВ «Агро-Трейд»"
    assert body["tax_id"] == "12345678"
    assert body["status"] == "active"

    fetched = await client.get(f"{SUPPLIERS}/{supplier_id}", headers=auth(token))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["company_name"] == "ТОВ «Агро-Трейд»"

    listing = await client.get(
        SUPPLIERS, headers=auth(token), params={"search": "Агро-Трейд"}
    )
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload["total"] >= 1
    assert supplier_id in {item["supplier_id"] for item in payload["items"]}

    patched = await client.patch(
        f"{SUPPLIERS}/{supplier_id}",
        headers=auth(token),
        json={"company_name": "ТОВ «Агро-Трейд» (новий)", "status": "inactive"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["company_name"] == "ТОВ «Агро-Трейд» (новий)"
    assert patched.json()["status"] == "inactive"
    assert patched.json()["tax_id"] == "12345678"  # не змінилося

    deleted = await client.delete(f"{SUPPLIERS}/{supplier_id}", headers=auth(token))
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"{SUPPLIERS}/{supplier_id}", headers=auth(token))).status_code == 404

async def test_recipient_crud_cycle(client: AsyncClient):
    token = await login(client, ADMIN)

    created = await client.post(
        RECIPIENTS,
        headers=auth(token),
        json={
            "company_name": "Магазин «Сільпо» №12",
            "tax_id": "1234567890",
            "contact_person": "Олена Ковальчук",
            "phone_number": "(044) 123-45-67",
            "email": "order@silpo.example",
            "address": "м. Львів, вул. Городоцька, 2",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    recipient_id = body["recipient_id"]
    assert body["address"] == "м. Львів, вул. Городоцька, 2"
    assert body["status"] == "active"

    fetched = await client.get(f"{RECIPIENTS}/{recipient_id}", headers=auth(token))
    assert fetched.status_code == 200, fetched.text

    patched = await client.patch(
        f"{RECIPIENTS}/{recipient_id}",
        headers=auth(token),
        json={"address": "м. Львів, вул. Липська, 5"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["address"] == "м. Львів, вул. Липська, 5"

    deleted = await client.delete(f"{RECIPIENTS}/{recipient_id}", headers=auth(token))
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"{RECIPIENTS}/{recipient_id}", headers=auth(token))).status_code == 404

async def test_supplier_field_validation(client: AsyncClient):
    token = await login(client, ADMIN)

    response = await client.post(
        SUPPLIERS, headers=auth(token), json={"company_name": "   "}
    )
    assert response.status_code == 422, response.text

    for bad_tax_id in ("123", "123456789", "abcdefgh"):
        response = await client.post(
            SUPPLIERS,
            headers=auth(token),
            json={"company_name": unique("ТОВ"), "tax_id": bad_tax_id},
        )
        assert response.status_code == 422, (bad_tax_id, response.text)

    response = await client.post(
        SUPPLIERS,
        headers=auth(token),
        json={"company_name": unique("ТОВ"), "phone_number": "абв"},
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        SUPPLIERS,
        headers=auth(token),
        json={"company_name": unique("ТОВ"), "email": "not-an-email"},
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        SUPPLIERS,
        headers=auth(token),
        json={"company_name": unique("ТОВ"), "email": f"{'a' * 120}@example.com"},
    )
    assert response.status_code == 422, response.text

    supplier_id = await create_supplier(client, token)
    response = await client.patch(
        f"{SUPPLIERS}/{supplier_id}", headers=auth(token), json={}
    )
    assert response.status_code == 422, response.text

async def test_recipient_field_validation(client: AsyncClient):
    token = await login(client, ADMIN)

    response = await client.post(
        RECIPIENTS, headers=auth(token), json={"address": "м. Львів"}
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        RECIPIENTS, headers=auth(token), json={"company_name": unique("ТОВ")}
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        RECIPIENTS,
        headers=auth(token),
        json={"company_name": unique("ТОВ"), "address": "   "},
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        RECIPIENTS,
        headers=auth(token),
        json={"company_name": unique("ТОВ"), "address": "м. Львів", "tax_id": "123"},
    )
    assert response.status_code == 422, response.text

    recipient_id = await create_recipient(client, token)
    response = await client.patch(
        f"{RECIPIENTS}/{recipient_id}", headers=auth(token), json={"status": None}
    )
    assert response.status_code == 422, response.text

async def test_duplicate_tax_id_is_rejected(client: AsyncClient):
    token = await login(client, ADMIN)
    tax_id = "87654321"
    await create_supplier(client, token, tax_id=tax_id)

    response = await client.post(
        SUPPLIERS,
        headers=auth(token),
        json={"company_name": unique("ТОВ"), "tax_id": tax_id},
    )
    assert response.status_code == 409, response.text

    other = await create_supplier(client, token)
    response = await client.patch(
        f"{SUPPLIERS}/{other}", headers=auth(token), json={"tax_id": tax_id}
    )
    assert response.status_code == 409, response.text

async def test_counterparty_without_referencing_orders_is_deletable(client: AsyncClient):
    
    token = await login(client, ADMIN)
    supplier_id = await create_supplier(client, token)
    assert (
        await client.delete(f"{SUPPLIERS}/{supplier_id}", headers=auth(token))
    ).status_code == 204

async def test_counterparties_require_manager_role(client: AsyncClient):
    
    worker_token = await login(client, WORKER)
    response = await client.get(SUPPLIERS, headers=auth(worker_token))
    assert response.status_code == 403, response.text

    manager_token = await login(client, MANAGER)
    response = await client.get(SUPPLIERS, headers=auth(manager_token))
    assert response.status_code == 200, response.text

    response = await client.post(
        SUPPLIERS, headers=auth(manager_token), json={"company_name": unique("ТОВ")}
    )
    assert response.status_code == 201, response.text

async def test_counterparties_require_authentication(client: AsyncClient):
    for url in (SUPPLIERS, RECIPIENTS):
        response = await client.get(url)
        assert response.status_code == 401, (url, response.text)
