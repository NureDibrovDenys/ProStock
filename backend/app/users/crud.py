"""CRUD-операції з користувачами."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RoleName, UserStatus
from app.users.models import Role, User
from app.utils.security import hash_password


class EmailAlreadyExistsError(Exception):
    """Email уже зайнятий іншим користувачем."""


class RoleNotFoundError(Exception):
    """Вказаної ролі не існує."""


async def get_role_by_name(session: AsyncSession, role_name: RoleName) -> Role | None:
    return await session.scalar(select(Role).where(Role.name == role_name))


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.scalar(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(
        select(User).options(selectinload(User.role)).where(User.email == email)
    )


async def list_users(
    session: AsyncSession,
    *,
    search: str | None = None,
    role: RoleName | None = None,
    status: UserStatus | None = None,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """Повертає сторінку користувачів і загальну кількість."""
    conditions = []

    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(User.email).like(pattern),
                func.lower(User.first_name).like(pattern),
                func.lower(User.last_name).like(pattern),
            )
        )
    if role is not None:
        conditions.append(User.role_id == select(Role.id).where(Role.name == role).scalar_subquery())
    if status is not None:
        conditions.append(User.status == status)
    if warehouse_id is not None:
        conditions.append(User.warehouse_id == warehouse_id)

    total = await session.scalar(
        select(func.count(User.id)).where(*conditions)
    ) or 0

    rows = (
        await session.scalars(
            select(User)
            .options(selectinload(User.role))
            .where(*conditions)
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return list(rows), total


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: RoleName,
    status: UserStatus = UserStatus.ACTIVE,
    warehouse_id: int | None = 1,
) -> User:
    if await session.scalar(select(User.id).where(User.email == email)):
        raise EmailAlreadyExistsError(email)

    role_model = await get_role_by_name(session, role)
    if role_model is None:
        raise RoleNotFoundError(role.value)

    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role_id=role_model.id,
        status=status,
        warehouse_id=warehouse_id or 1,
    )
    session.add(user)
    await session.commit()
    return await get_user(session, user.id)  # type: ignore[return-value]


async def update_user(
    session: AsyncSession,
    user: User,
    *,
    email: str | None = None,
    password: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    role: RoleName | None = None,
    status: UserStatus | None = None,
    warehouse_id: int | None | type[...] = ...,  # sentinel: ... = не змінювати
) -> User:
    if email is not None and email != user.email:
        exists = await session.scalar(
            select(User.id).where(User.email == email, User.id != user.id)
        )
        if exists:
            raise EmailAlreadyExistsError(email)
        user.email = email

    if password is not None:
        user.password_hash = hash_password(password)
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if status is not None:
        user.status = status
    # warehouse_id: None — явно відв'язати, int — прив'язати, ... — не чіпати
    if warehouse_id is not ...:
        user.warehouse_id = warehouse_id  # type: ignore[assignment]

    if role is not None and (user.role is None or user.role.name != role):
        role_model = await get_role_by_name(session, role)
        if role_model is None:
            raise RoleNotFoundError(role.value)
        user.role_id = role_model.id
        user.role = role_model

    await session.commit()
    return await get_user(session, user.id)  # type: ignore[return-value]


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()


async def count_active_admins(session: AsyncSession, exclude_user_id: int | None = None) -> int:
    """Кількість активних root/адміністраторів (для захисту від блокування системи)."""
    admin_role_ids = select(Role.id).where(Role.name.in_([RoleName.ROOT, RoleName.ADMIN]))
    conditions = [
        User.role_id.in_(admin_role_ids),
        User.status == UserStatus.ACTIVE,
    ]
    if exclude_user_id is not None:
        conditions.append(User.id != exclude_user_id)
    return await session.scalar(select(func.count(User.id)).where(*conditions)) or 0
