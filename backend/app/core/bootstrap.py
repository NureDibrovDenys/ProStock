"""Ідемпотентне наповнення довідника ролей та стартових користувачів."""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import RoleName, UserStatus
from app.users.models import Role, User

logger = logging.getLogger("prostock.bootstrap")

DEFAULT_USERS: tuple[tuple[str, str, str, str, RoleName], ...] = (
    ("Адмін", "Системи", "ADMIN_EMAIL", "ADMIN_PASSWORD", RoleName.ADMIN),
    ("Олена", "Ковальчук", "MANAGER_EMAIL", "MANAGER_PASSWORD", RoleName.WAREHOUSE_MANAGER),
    ("Іван", "Петренко", "WORKER_EMAIL", "WORKER_PASSWORD", RoleName.WORKER),
)
DEFAULT_WAREHOUSE_ID = 1


async def ensure_roles(session: AsyncSession) -> dict[RoleName, Role]:
    """Створює відсутні ролі й повертає мапу name → Role."""
    existing = {role.name: role for role in (await session.scalars(select(Role))).all()}
    for role_name in RoleName:
        if role_name not in existing:
            role = Role(name=role_name)
            session.add(role)
            existing[role_name] = role
            logger.info("Створено роль %s", role_name.value)
    await session.flush()
    return existing


async def ensure_default_users(session: AsyncSession, roles: dict[RoleName, Role]) -> None:
    """Створює стартові акаунти, якщо їх ще немає (лише коли SEED_DEFAULT_USERS)."""
    # Імпорт усередині функції, щоб уникнути циклічної залежності
    from app.utils.security import hash_password

    for first_name, last_name, email_setting, password_setting, role_name in DEFAULT_USERS:
        email = getattr(settings, email_setting).strip().lower()
        password = getattr(settings, password_setting)
        if not email:
            continue

        exists = await session.scalar(select(User.id).where(User.email == email))
        if exists:
            continue

        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                role_id=roles[role_name].id,
                status=UserStatus.ACTIVE,
                warehouse_id=DEFAULT_WAREHOUSE_ID,
            )
        )
        logger.info("Створено стартового користувача %s (%s)", email, role_name.value)


async def ensure_default_warehouse(session: AsyncSession) -> None:
    """Створює склад за замовчуванням, якщо складів ще немає (з ним працює редактор мапи)."""
    from app.warehouses.models import Warehouse

    if await session.scalar(select(Warehouse.id).limit(1)):
        return
    # Площа-заглушка: перерахується з контуру стін під час першого збереження мапи
    session.add(Warehouse(name="Основний склад", total_area=Decimal("1.00")))
    logger.info("Створено склад за замовчуванням")


async def bootstrap(session: AsyncSession) -> None:
    roles = await ensure_roles(session)
    if settings.SEED_DEFAULT_USERS:
        await ensure_default_users(session, roles)
    await ensure_default_warehouse(session)
    from app.warehouses.models import Warehouse

    if await session.scalar(select(Warehouse.id).where(Warehouse.id == DEFAULT_WAREHOUSE_ID)):
        await session.execute(
            update(User)
            .where(User.warehouse_id.is_(None))
            .values(warehouse_id=DEFAULT_WAREHOUSE_ID)
        )
    await session.commit()
