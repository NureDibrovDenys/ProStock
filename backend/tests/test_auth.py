"""Тести авторизації: вхід, refresh-ротація, профіль, вихід, cookie."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.utils import ADMIN, API, WORKER, auth, login


async def test_login_returns_access_token_and_profile(client: AsyncClient):
    response = await client.post(
        f"{API}/auth/login",
        json={"email": ADMIN[0], "password": ADMIN[1]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert data["user"]["user_email"] == ADMIN[0]
    assert data["user"]["role"] == "administrator"
    assert data["user"]["permissions"]["users_manage"] is True


async def test_login_sets_secure_refresh_cookie(client: AsyncClient):
    response = await client.post(
        f"{API}/auth/login",
        json={"email": ADMIN[0], "password": ADMIN[1]},
    )
    cookie_header = response.headers["set-cookie"]
    assert "prostock_refresh=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/api/v1/auth" in cookie_header
    assert "samesite=lax" in cookie_header.lower()
    assert response.headers["cache-control"] == "no-store"


async def test_login_rejects_wrong_password_and_unknown_email(client: AsyncClient):
    wrong = await client.post(
        f"{API}/auth/login", json={"email": ADMIN[0], "password": "WrongPass123"}
    )
    unknown = await client.post(
        f"{API}/auth/login", json={"email": "ghost@prostock.com", "password": "WrongPass123"}
    )
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


async def test_login_validates_email_format(client: AsyncClient):
    response = await client.post(
        f"{API}/auth/login", json={"email": "not-an-email", "password": "x"}
    )
    assert response.status_code == 422


async def test_me_requires_token(client: AsyncClient):
    response = await client.get(f"{API}/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_profile(client: AsyncClient):
    token = await login(client, ADMIN)
    response = await client.get(f"{API}/auth/me", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["permissions"]["products_write"] is True


async def test_refresh_rotates_token(client: AsyncClient):
    await login(client, ADMIN)
    old_cookie = client.cookies.get("prostock_refresh")
    assert old_cookie

    response = await client.post(f"{API}/auth/refresh")
    assert response.status_code == 200
    new_cookie = client.cookies.get("prostock_refresh")
    assert new_cookie != old_cookie

    # Старий refresh уже відкликано
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        other.cookies.set("prostock_refresh", old_cookie, path="/api/v1/auth")
        reuse = await other.post(f"{API}/auth/refresh")
        assert reuse.status_code == 401


async def test_refresh_without_cookie_is_unauthorized(client: AsyncClient):
    response = await client.post(f"{API}/auth/refresh")
    assert response.status_code == 401


async def test_logout_revokes_session(client: AsyncClient):
    await login(client, ADMIN)
    response = await client.post(f"{API}/auth/logout")
    assert response.status_code == 200
    assert client.cookies.get("prostock_refresh") is None
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401


async def test_blocked_user_cannot_login_or_use_old_token(client: AsyncClient):
    token = await login(client, ADMIN)

    users = await client.get(
        f"{API}/users", headers=auth(token), params={"search": WORKER[0]}
    )
    worker_id = users.json()["items"][0]["user_id"]

    worker_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    async with worker_client:
        worker_token = await login(worker_client, WORKER)

        blocked = await client.patch(
            f"{API}/users/{worker_id}",
            headers=auth(token),
            json={"status": "blocked"},
        )
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "blocked"

        # Старий токен заблокованого користувача більше не працює
        denied = await worker_client.get(f"{API}/products", headers=auth(worker_token))
        assert denied.status_code == 403

        relogin = await worker_client.post(
            f"{API}/auth/login",
            json={"email": WORKER[0], "password": WORKER[1]},
        )
        assert relogin.status_code == 403

        # Повертаємо доступність для інших тестів
        restored = await client.patch(
            f"{API}/users/{worker_id}",
            headers=auth(token),
            json={"status": "active"},
        )
        assert restored.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "", "password": ""},
        {"email": ADMIN[0]},
        {"password": ADMIN[1]},
    ],
)
async def test_login_requires_both_fields(client: AsyncClient, payload: dict):
    response = await client.post(f"{API}/auth/login", json=payload)
    assert response.status_code == 422
