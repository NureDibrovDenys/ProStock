"""Менеджер складу: створення, перегляд і редагування комірників свого складу."""
from __future__ import annotations

from httpx import AsyncClient

from tests.utils import ADMIN, API, MANAGER, WORKER, auth, login, unique

STOREKEEPERS = f"{API}/managers/storekeepers"


async def _create_storekeeper(client: AsyncClient, token: str) -> dict:
    response = await client.post(
        STOREKEEPERS,
        headers=auth(token),
        json={
            "first_name": "Іван",
            "last_name": "Комірник",
            "user_email": f"{unique('sk')}@prostock.com",
            "password": "Worker12345",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_manager_lists_only_own_storekeepers(client: AsyncClient):
    manager_token = await login(client, MANAGER)
    created = await _create_storekeeper(client, manager_token)

    response = await client.get(STOREKEEPERS, headers=auth(manager_token), params={"page_size": 100})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert any(item["user_id"] == created["user_id"] for item in items)
    assert all(item["role"] == "storekeeper" for item in items)
    assert all(item["warehouse_id"] == created["warehouse_id"] for item in items)


async def test_manager_updates_storekeeper_profile_and_password(client: AsyncClient):
    manager_token = await login(client, MANAGER)
    created = await _create_storekeeper(client, manager_token)
    new_email = f"{unique('sk-new')}@prostock.com"

    response = await client.patch(
        f"{STOREKEEPERS}/{created['user_id']}",
        headers=auth(manager_token),
        json={"first_name": "Петро", "last_name": "Оновлений", "user_email": new_email, "password": "NewPass12345"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["first_name"], body["last_name"], body["user_email"]) == ("Петро", "Оновлений", new_email)
    assert body["role"] == "storekeeper"

    # Новий пароль працює, старий — ні
    assert (await client.post(f"{API}/auth/login", json={"email": new_email, "password": "NewPass12345"})).status_code == 200
    assert (await client.post(f"{API}/auth/login", json={"email": new_email, "password": "Worker12345"})).status_code == 401


async def test_manager_cannot_take_existing_email(client: AsyncClient):
    manager_token = await login(client, MANAGER)
    created = await _create_storekeeper(client, manager_token)

    response = await client.patch(
        f"{STOREKEEPERS}/{created['user_id']}",
        headers=auth(manager_token),
        json={"user_email": ADMIN[0]},
    )
    assert response.status_code == 409


async def test_manager_cannot_edit_non_storekeepers(client: AsyncClient):
    manager_token = await login(client, MANAGER)
    me = (await client.get(f"{API}/auth/me", headers=auth(manager_token))).json()

    # Сам менеджер і адміністратор — не комірники: для менеджера їх «не існує»
    for user_id in (me["user_id"], 1):
        response = await client.patch(
            f"{STOREKEEPERS}/{user_id}", headers=auth(manager_token), json={"first_name": "Хакер"}
        )
        assert response.status_code == 404, response.text
        assert (await client.get(f"{STOREKEEPERS}/{user_id}", headers=auth(manager_token))).status_code == 404


async def test_manager_cannot_change_role_through_update(client: AsyncClient):
    manager_token = await login(client, MANAGER)
    created = await _create_storekeeper(client, manager_token)

    response = await client.patch(
        f"{STOREKEEPERS}/{created['user_id']}",
        headers=auth(manager_token),
        json={"role": "administrator", "warehouse_id": 999, "status": "inactive"},
    )
    # Зайві поля ігноруються: роль, склад і статус не змінюються
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "storekeeper"
    assert body["warehouse_id"] == created["warehouse_id"]
    assert body["status"] == "active"


async def test_other_roles_cannot_use_manager_endpoints(client: AsyncClient):
    for credentials in (ADMIN, WORKER):
        token = await login(client, credentials)
        assert (await client.get(STOREKEEPERS, headers=auth(token))).status_code == 403
        assert (await client.patch(f"{STOREKEEPERS}/1", headers=auth(token), json={"first_name": "X"})).status_code == 403
