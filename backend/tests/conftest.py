"""Фікстури інтеграційних тестів: окрема БД prostock_test і ASGI-клієнт."""
from __future__ import annotations

import os

# Важливо: змінні мають бути виставлені ДО імпорту налаштувань застосунку
os.environ["DB_NAME"] = "prostock_test"
os.environ["SEED_DEFAULT_USERS"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"
os.environ["LOGIN_MAX_ATTEMPTS"] = "100"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from sqlalchemy import update

from app.core.bootstrap import bootstrap, ensure_default_warehouse
from app.users.models import User
from app.core.db import Base, async_session_maker, engine
from app.main import app

API = "/api/v1"


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def prepared_database():
    """Чиста тестова БД на весь сеанс тестів."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        await bootstrap(session)
        # Bootstrap не призначає склади: як і в житті, адміністратор прив'язує персонал до складу
        warehouse_id = await ensure_default_warehouse(session)
        await session.execute(
            update(User)
            .where(User.email.in_([os.environ.get("MANAGER_EMAIL", "manager@prostock.com"),
                                   os.environ.get("WORKER_EMAIL", "worker@prostock.com")]))
            .values(warehouse_id=warehouse_id)
        )
        await session.commit()

    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
