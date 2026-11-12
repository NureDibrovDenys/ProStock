from __future__ import annotations
from decimal import Decimal
from httpx import AsyncClient

from app.core.db import async_session_maker
from app.warehouses.models import Warehouse
from tests.utils import ADMIN, API, auth, login, unique

STOREKEEPERS = f"{API}/managers/storekeepers"
PASSWORD = "Worker12345"

async def _admin_creates_manager(client: AsyncClient, admin_token: str) -> dict:
    email = f"{unique('mgr')}@prostock.com"
    response = await client.post(
        f"{API}/users",
        headers=auth(admin_token),
        json={
            "first_name": "Марія",
            "last_name": "Менеджер",
            "user_email": email,
            "password": "Manager12345",
            "role": "warehouse_manager",
        },
    )
    assert response.status_code == 201, response.text
    manager = response.json()
    manager["password"] = "Manager12345"
    return manager


async def _assign_warehouse(client: AsyncClient, admin_token: str, user_id: int, warehouse_id: int | None):
    return await client.put(
        f"{API}/users/{user_id}/warehouse",
        headers=auth(admin_token),
        json={"warehouse_id": warehouse_id},
    )


def _storekeeper_payload(**overrides) -> dict:
    payload = {
        "first_name": "Іван",
        "last_name": "Комірник",
        "user_email": f"{unique('sk')}@prostock.com",
        "password": PASSWORD,
    }
    payload.update(overrides)
    return payload


async def _create_second_warehouse() -> int:
    async with async_session_maker() as session:
        warehouse = Warehouse(name=unique("Другий склад"), total_area=Decimal("1.00"))
        session.add(warehouse)
        await session.commit()
        return warehouse.id

async def test_full_flow_admin_manager_storekeeper(client: AsyncClient):
    admin_token = await login(client, ADMIN)

    #Адмін створює менеджера, без призначення складу
    manager = await _admin_creates_manager(client, admin_token)
    assert manager["role"] == "warehouse_manager"
    assert manager["warehouse_id"] is None

    manager_token = await login(client, (manager["user_email"], manager["password"]))

    #Менеджер без складу не може створити комірника
    blocked = await client.post(STOREKEEPERS, headers=auth(manager_token), json=_storekeeper_payload())
    assert blocked.status_code == 403, blocked.text

    #Адмін призначає склад для створеного менеджера
    assigned = await _assign_warehouse(client, admin_token, manager["user_id"], 1)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["warehouse_id"] == 1

    #Менеджер створює комірника, роль і склад виставляє сервер
    payload = _storekeeper_payload()
    created = await client.post(STOREKEEPERS, headers=auth(manager_token), json=payload)
    assert created.status_code == 201, created.text
    storekeeper = created.json()
    assert storekeeper["role"] == "storekeeper"
    assert storekeeper["warehouse_id"] == 1
    assert storekeeper["status"] == "active"
    assert "password" not in storekeeper and "password_hash" not in storekeeper

    #Комірник входить в систему
    storekeeper_token = await login(client, (payload["user_email"], PASSWORD))
    me = (await client.get(f"{API}/auth/me", headers=auth(storekeeper_token))).json()
    assert me["role"] == "storekeeper"
    assert me["permissions"]["products_write"] is False
    assert me["permissions"]["storekeepers_manage"] is False

    #Комірник з'являється у списку менеджера
    listing = await client.get(STOREKEEPERS, headers=auth(manager_token), params={"page_size": 100})
    assert listing.status_code == 200, listing.text
    assert storekeeper["user_id"] in {item["user_id"] for item in listing.json()["items"]}

    #Комірник не може створювати інших комірників
    forbidden = await client.post(STOREKEEPERS, headers=auth(storekeeper_token), json=_storekeeper_payload())
    assert forbidden.status_code == 403

async def test_manager_cannot_escalate_role_on_create(client: AsyncClient):
    """Додаткові поля role/warehouse_id у запиті ігноруються: створюється лише комірник свого складу."""
    admin_token = await login(client, ADMIN)
    manager = await _admin_creates_manager(client, admin_token)
    await _assign_warehouse(client, admin_token, manager["user_id"], 1)
    manager_token = await login(client, (manager["user_email"], manager["password"]))

    other_warehouse = await _create_second_warehouse()
    response = await client.post(
        STOREKEEPERS,
        headers=auth(manager_token),
        json=_storekeeper_payload(role="administrator", warehouse_id=other_warehouse),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "storekeeper"
    assert body["warehouse_id"] == 1

async def test_storekeeper_creation_validation(client: AsyncClient):
    admin_token = await login(client, ADMIN)
    manager = await _admin_creates_manager(client, admin_token)
    await _assign_warehouse(client, admin_token, manager["user_id"], 1)
    token = await login(client, (manager["user_email"], manager["password"]))

    first = _storekeeper_payload()
    assert (await client.post(STOREKEEPERS, headers=auth(token), json=first)).status_code == 201

    #дублювання пошти (без урахування регістру)
    duplicate = await client.post(
        STOREKEEPERS, headers=auth(token), json=_storekeeper_payload(user_email=first["user_email"].upper())
    )
    assert duplicate.status_code == 409, duplicate.text

    # слабкий пароль, некоректний email, порожнє імʼя
    for bad in (
            {"password": "12345678"},
            {"user_email": "not email"},
            {"first_name": ""},
            {"last_name": ""},
    ):
        response = await client.post(STOREKEEPERS, headers=auth(token), json=_storekeeper_payload(**bad))
        assert response.status_code == 422, (bad, response.text)

    #без токена
    assert (await client.post(STOREKEEPERS, json=_storekeeper_payload())).status_code == 401

async def test_managers_are_isolated_by_warehouse(client: AsyncClient):
    admin_token = await login(client, ADMIN)
    manager_a = await _admin_creates_manager(client, admin_token)
    manager_b = await _admin_creates_manager(client, admin_token)
    second_warehouse = await _create_second_warehouse()
    assert (await _assign_warehouse(client, admin_token, manager_a["user_id"], 1)).status_code == 200
    assert (await _assign_warehouse(client, admin_token, manager_b["user_id"], second_warehouse)).status_code == 200

    token_a = await login(client, (manager_a["user_email"], manager_a["password"]))
    token_b = await login(client, (manager_b["user_email"], manager_b["password"]))

    created = await client.post(STOREKEEPERS, headers=auth(token_a), json=_storekeeper_payload())
    assert created.status_code == 201, created.text
    storekeeper_id = created.json()["user_id"]

    # менеджер B не бачить, не читає й не редагує комірника складу A
    listing = await client.get(STOREKEEPERS, headers=auth(token_b), params={"page_size": 100})
    assert storekeeper_id not in {item["user_id"] for item in listing.json()["items"]}
    assert (await client.get(f"{STOREKEEPERS}/{storekeeper_id}", headers=auth(token_b))).status_code == 404
    patched = await client.patch(
        f"{STOREKEEPERS}/{storekeeper_id}", headers=auth(token_b), json={"first_name": "Хакер"}
    )
    assert patched.status_code == 404

    #менеджер A бачить і може редагувати
    assert (await client.get(f"{STOREKEEPERS}/{storekeeper_id}", headers=auth(token_a))).status_code == 200

async def test_warehouse_assignment_rules(client: AsyncClient):
    admin_token = await login(client, ADMIN)
    manager = await _admin_creates_manager(client, admin_token)

    #неіснуючий склад та неіснуючий користувач
    assert (await _assign_warehouse(client, admin_token, manager["user_id"], 99999)).status_code == 404
    assert (await _assign_warehouse(client, admin_token, 99999, 1)).status_code == 404

    #склад можна призначати лише менеджеру (перевірка призначення адміна)
    me = (await client.get(f"{API}/auth/me", headers=auth(admin_token))).json()
    assert (await _assign_warehouse(client, admin_token, me["user_id"], 1)).status_code == 422

    #менеджер не може призначати склад
    await _assign_warehouse(client, admin_token, manager["user_id"], 1)
    manager_token = await login(client, (manager["user_email"], manager["password"]))
    own = await _assign_warehouse(client, manager_token, manager["user_id"], 1)
    assert own.status_code == 403

    #зняття призначення повертає менеджера у стан «без складу»
    assert (await _assign_warehouse(client, admin_token, manager["user_id"], None)).status_code == 200
    blocked = await client.post(STOREKEEPERS, headers=auth(manager_token), json=_storekeeper_payload())
    assert blocked.status_code == 403