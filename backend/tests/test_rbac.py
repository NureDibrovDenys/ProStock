"""RBAC: права різних ролей на товари, користувачів і мапу."""
from __future__ import annotations

from httpx import AsyncClient

from tests.utils import ADMIN, API, MANAGER, WORKER, auth, create_category, login, product_payload


async def test_anonymous_has_no_access(client: AsyncClient):
    assert (await client.get(f"{API}/products")).status_code == 401
    assert (await client.get(f"{API}/categories")).status_code == 401
    assert (await client.get(f"{API}/users")).status_code == 401


async def test_worker_can_read_but_not_write(client: AsyncClient):
    admin_token = await login(client, ADMIN)
    category_id = await create_category(client, admin_token)

    worker_token = await login(client, WORKER)
    payload = product_payload(category_id)

    assert (await client.get(f"{API}/products", headers=auth(worker_token))).status_code == 200
    created = await client.post(f"{API}/products", headers=auth(worker_token), json=payload)
    assert created.status_code == 403, created.text
    assert (await client.get(f"{API}/products/export", headers=auth(worker_token))).status_code == 200
    assert (
        await client.post(
            f"{API}/products/import",
            headers=auth(worker_token),
            files={"file": ("a.csv", b"x", "text/csv")},
        )
    ).status_code == 403
    assert (await client.get(f"{API}/users", headers=auth(worker_token))).status_code == 403
    assert (await client.post(f"{API}/categories", headers=auth(worker_token), json={"name": "X"})).status_code == 403


async def test_manager_can_write_but_not_delete_or_manage_users(client: AsyncClient):
    admin_token = await login(client, ADMIN)
    category_id = await create_category(client, admin_token)
    manager_token = await login(client, MANAGER)

    created = await client.post(
        f"{API}/products", headers=auth(manager_token), json=product_payload(category_id)
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["product_id"]

    patched = await client.patch(
        f"{API}/products/{product_id}",
        headers=auth(manager_token),
        json={"name": "Оновлено менеджером"},
    )
    assert patched.status_code == 200

    denied_delete = await client.delete(f"{API}/products/{product_id}", headers=auth(manager_token))
    assert denied_delete.status_code == 403

    denied_users = await client.get(f"{API}/users", headers=auth(manager_token))
    assert denied_users.status_code == 403

    # Прибирає адміністратор
    assert (await client.delete(f"{API}/products/{product_id}", headers=auth(admin_token))).status_code == 204


async def test_admin_can_delete_product(client: AsyncClient):
    admin_token = await login(client, ADMIN)
    category_id = await create_category(client, admin_token)
    created = await client.post(
        f"{API}/products", headers=auth(admin_token), json=product_payload(category_id)
    )
    product_id = created.json()["product_id"]

    assert (await client.delete(f"{API}/products/{product_id}", headers=auth(admin_token))).status_code == 204
    assert (await client.get(f"{API}/products/{product_id}", headers=auth(admin_token))).status_code == 404


async def test_permissions_payload_matches_role(client: AsyncClient):
    worker_token = await login(client, WORKER)
    me = (await client.get(f"{API}/auth/me", headers=auth(worker_token))).json()
    assert me["permissions"] == {
        "products_read": True,
        "products_write": False,
        "products_delete": False,
        "products_import": False,
        "products_export": True,
        "users_manage": False,
        "warehouse_map_write": False,
    }
