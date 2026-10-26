import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.bootstrap import bootstrap
from app.core.config import settings
from app.core.db import async_session_maker
from app.products.router import categories_router, router as products_router
from app.routers import auth as auth_router
from app.routers import map as map_router
from app.users.router import router as users_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("prostock")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Готує довідник ролей і стартові акаунти (ідемпотентно)."""
    try:
        async with async_session_maker() as session:
            await bootstrap(session)
    except Exception:  # noqa: BLE001 — не валимо API, якщо БД тимчасово недоступна
        logger.exception("Не вдалося виконати bootstrap бази даних")
    yield


app = FastAPI(
    title="ProStock API",
    description="Backend API для системи управління ProStock",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
)

#підключення роутера для роботи з топологією складу
app.include_router(map_router.router)

#роутери автентифікації, користувачів, товарів
app.include_router(auth_router.router)
app.include_router(users_router)
app.include_router(products_router)
app.include_router(categories_router)


@app.get("/")
def root():
    return {
        "message": "API ProStock працює!",
        "docs": "/docs",
        "version": app.version,
    }


@app.get("/api/v1/health", tags=["Service"])
async def health():
    """Перевірка доступності API та бази даних."""
    from sqlalchemy import text
    from app.core.db import async_session_maker as session_maker

    database_ok = True
    try:
        async with session_maker() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        database_ok = False

    return {"status": "ok" if database_ok else "degraded", "database": database_ok}
