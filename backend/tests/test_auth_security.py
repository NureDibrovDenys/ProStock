"""Негативні сценарії токенів: підпис, тип, строк дії, схема авторизації."""
from __future__ import annotations

from datetime import timedelta

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.utils.security import create_access_token
from tests.utils import ADMIN, API, auth, login


async def test_tampered_access_token_is_rejected(client: AsyncClient):
    token = await login(client, ADMIN)
    tampered = token[:-3] + ("abc" if not token.endswith("abc") else "xyz")

    response = await client.get(f"{API}/auth/me", headers=auth(tampered))
    assert response.status_code == 401


async def test_expired_access_token_is_rejected(client: AsyncClient):
    expired, _ = create_access_token(
        subject=ADMIN[0],
        user_id=1,
        role="administrator",
        expires_delta=timedelta(seconds=-5),
    )

    response = await client.get(f"{API}/auth/me", headers=auth(expired))
    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_access(client: AsyncClient):
    await login(client, ADMIN)
    refresh_token = client.cookies.get("prostock_refresh")
    assert refresh_token

    response = await client.get(f"{API}/auth/me", headers=auth(refresh_token))
    assert response.status_code == 401


async def test_access_token_cannot_be_used_as_refresh(client: AsyncClient):
    access_token = await login(client, ADMIN)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        other.cookies.set("prostock_refresh", access_token, path="/api/v1/auth")
        response = await other.post(f"{API}/auth/refresh")
        assert response.status_code == 401


async def test_non_bearer_scheme_is_rejected(client: AsyncClient):
    token = await login(client, ADMIN)

    response = await client.get(f"{API}/auth/me", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 401
