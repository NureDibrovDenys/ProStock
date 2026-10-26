"""CRUD користувачів і захист від блокування системи."""
from __future__ import annotations

from httpx import AsyncClient

from tests.utils import ADMIN, API, auth, login, unique


def user_payload(email: str | None = None, **overrides) -> dict:
    payload = {
        "first_name": "Тест",
        "last_name": "Тестовий",
        "user_email": email or f"{unique('user')}@prostock.ua",
        "password": "Tester12345",
        "role": "storekeeper",
        "warehouse_id": 1,
    }
    payload.update(overrides)
    return payload


async def test_user_crud(client: AsyncClient):
    token = await login(client, ADMIN)

    created = await client.post(f"{API}/users", headers=auth(token), json=user_payload())
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["role"] == "storekeeper"
    assert user["status"] == "active"

    listed = await client.get(f"{API}/users", headers=auth(token), params={"search": user["user_email"]})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = await client.get(f"{API}/users/{user['user_id']}", headers=auth(token))
    assert fetched.status_code == 200

    patched = await client.patch(
        f"{API}/users/{user['user_id']}",
        headers=auth(token),
        json={"first_name": "Нове", "role": "warehouse_manager"},
    )
    assert patched.status_code == 200
    assert patched.json()["first_name"] == "Нове"
    assert patched.json()["role"] == "warehouse_manager"

    assert (await client.delete(f"{API}/users/{user['user_id']}", headers=auth(token))).status_code == 204
    assert (await client.get(f"{API}/users/{user['user_id']}", headers=auth(token))).status_code == 404


async def test_duplicate_email_conflict(client: AsyncClient):
    token = await login(client, ADMIN)
    email = f"{unique('dup')}@prostock.ua"
    assert (await client.post(f"{API}/users", headers=auth(token), json=user_payload(email))).status_code == 201
    duplicate = await client.post(f"{API}/users", headers=auth(token), json=user_payload(email))
    assert duplicate.status_code == 409


async def test_password_policy_on_user_create(client: AsyncClient):
    token = await login(client, ADMIN)
    weak = await client.post(f"{API}/users", headers=auth(token), json=user_payload(password="12345678"))
    assert weak.status_code == 422
    no_upper = await client.post(f"{API}/users", headers=auth(token), json=user_payload(password="test12345"))
    assert no_upper.status_code == 422


async def test_cannot_delete_self(client: AsyncClient):
    token = await login(client, ADMIN)
    me = (await client.get(f"{API}/auth/me", headers=auth(token))).json()
    response = await client.delete(f"{API}/users/{me['user_id']}", headers=auth(token))
    assert response.status_code == 409


async def test_cannot_deactivate_last_admin(client: AsyncClient):
    token = await login(client, ADMIN)
    me = (await client.get(f"{API}/auth/me", headers=auth(token))).json()

    # У тестовій БД є лише один адміністратор — самодективація заборонена
    response = await client.patch(
        f"{API}/users/{me['user_id']}", headers=auth(token), json={"status": "inactive"}
    )
    assert response.status_code == 409


async def test_users_endpoint_requires_admin(client: AsyncClient):
    from tests.utils import WORKER

    worker_token = await login(client, WORKER)
    assert (await client.get(f"{API}/users", headers=auth(worker_token))).status_code == 403
    assert (
        await client.post(f"{API}/users", headers=auth(worker_token), json=user_payload())
    ).status_code == 403
