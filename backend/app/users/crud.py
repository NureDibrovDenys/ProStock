from __future__ import annotations

from types import EllipsisType

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from collections.abc import Sequence
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.enums import RoleName, UserStatus
from app.users.models import Role, User
from app.utils.security import hash_password

from pydantic import EmailStr

from app.warehouses.models import Warehouse


class EmailAlreadyExistsError(Exception):
    """The email is already taken by another user."""
    pass

class RoleNotFoundError(Exception):
    """The specified role does not exist."""
    pass

class FailedToCreateUserError(Exception):
    """Failed to create the user in the DB."""
    pass

class FailedToUpdateUserError(Exception):
    """Failed to update the user in the DB."""
    pass

class UserCannotBeDeletedError(Exception):
    """The user cannot be deleted."""
    pass

class FailedToDeleteUserError(Exception):
    """The user cannot be deleted."""
    pass

class UserNotFoundError(Exception):
    """The user does not exist."""
    pass

class WareHouseNotFoundError(Exception):
    """Warehouse does not exist"""
    pass

class UserIsNotManagerError(Exception):
    """User is not a warehouse manager"""
    pass

class WarehouseRequiredForStorekeeperError(Exception):
    """A storekeeper cannot be created or left without a warehouse."""
    pass

class ManagerHasStorekeepersError(Exception):
    """The manager's warehouse cannot be changed: storekeepers would be orphaned."""
    pass

# PostgreSQL SQLSTATE codes we need to tell constraint violations apart
UNIQUE_VIOLATION: str = "23505"


def _pg_code(exc: SQLAlchemyError) -> str | None:
    """SQLSTATE of the underlying driver error (asyncpg / psycopg2)."""
    original = getattr(exc, "orig", None)
    return getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)


async def _ensure_warehouse_exists(
    session: AsyncSession,
    warehouse_id: int | None,
) -> None:
    """Guards against a dangling warehouse_id: without it the FK violation
    surfaces as an opaque IntegrityError and is reported as a wrong field."""
    if warehouse_id is None:
        return

    warehouse_exists = await session.scalar(
        select(Warehouse.id).where(Warehouse.id == warehouse_id)
    )
    if warehouse_exists is None:
        raise WareHouseNotFoundError(warehouse_id)


async def count_storekeepers(
    session: AsyncSession,
    warehouse_id: int,
) -> int:
    """Number of storekeepers assigned to a warehouse."""
    stmt = (
        select(func.count(User.id))
        .select_from(User)
        .join(User.role)
        .where(
            Role.name == RoleName.WORKER,
            User.warehouse_id == warehouse_id,
        )
    )
    return await session.scalar(stmt) or 0


async def count_active_managers(
    session: AsyncSession,
    warehouse_id: int,
    exclude_user_id: int | None = None,
) -> int:
    """Number of active warehouse managers responsible for a warehouse."""
    conditions = [
        Role.name == RoleName.WAREHOUSE_MANAGER,
        User.status == UserStatus.ACTIVE,
        User.warehouse_id == warehouse_id,
    ]

    if exclude_user_id is not None:
        conditions.append(User.id != exclude_user_id)

    stmt = (
        select(func.count(User.id))
        .select_from(User)
        .join(User.role)
        .where(*conditions)
    )
    return await session.scalar(stmt) or 0


async def get_role_by_name(
    session: AsyncSession,
    role_name: RoleName
) -> Role | None:
    stmt = (
        select(Role)
        .where(Role.name == role_name)
    )
    
    role: Role | None = await session.scalar(stmt)
    return role


async def get_user(
    session: AsyncSession,
    user_id: int,
    *,
    options: Sequence[LoaderOption] | None = None,
) -> User | None:
    """
    Finds a user by ID.
    
    By default, it retrieves the role,
    but these options can be overridden or disabled.
    """
    if options is None:
        options = [
            joinedload(
                User.role,
                innerjoin=True
            )
        ]
    
    user = await session.get(
        User,
        user_id,
        options=options
    )
    return user


async def get_user_by_email(
    session: AsyncSession,
    user_email: EmailStr
) -> User | None:
    stmt = (
        select(User)
        .options(
            joinedload(
                User.role,
                innerjoin=True
            )
        )
        .where(User.email == user_email)
    )
    
    user: User | None = await session.scalar(stmt)
    return user


async def list_users(
    session: AsyncSession,
    *,
    search: str | None = None,
    role_name: RoleName | None = None,
    user_status: UserStatus | None = None,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """Returns a page of users and the total number of users."""

    conditions: list = []

    if warehouse_id is not None:
        conditions.append(User.warehouse_id == warehouse_id)

    if search and search.strip():
        pattern: str = f"%{search.strip()}%"
        conditions.append(
            or_(
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
        )
    
    if role_name is not None:
        role_subquery = (
            select(Role.id)
            .where(Role.name == role_name)
            .scalar_subquery()
        )
        conditions.append(User.role_id == role_subquery)
    
    if user_status is not None:
        conditions.append(User.status == user_status)
        
    
    count_stmt = (
        select(func.count(User.id))
        .where(*conditions)
    )
    
    count_stmt_result = await session.scalar(count_stmt)
    total: int = count_stmt_result or 0
    
    users_stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(*conditions)
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
   
    
    rows_result = await session.scalars(users_stmt)
    rows = rows_result.all()
    return list(rows), total


async def create_user(
    session: AsyncSession,
    *,
    user_email: EmailStr,
    password: str,
    first_name: str,
    last_name: str,
    role_name: RoleName,
    user_status: UserStatus = UserStatus.ACTIVE,
    warehouse_id: int | None = None
) -> User:
    user_id_stmt = (
        select(User.id)
        .where(User.email == user_email)
    )
    existing_user_id = await session.scalar(user_id_stmt)
    if existing_user_id is not None:
        raise EmailAlreadyExistsError(user_email)

    role: Role | None = await get_role_by_name(session, role_name)
    if role is None:
        raise RoleNotFoundError(role_name.value)

    await _ensure_warehouse_exists(session, warehouse_id)
    if role_name == RoleName.WORKER and warehouse_id is None:
        raise WarehouseRequiredForStorekeeperError(
            "A storekeeper must be assigned to a warehouse"
        )

    user: User = User(
        email=user_email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role_id=role.id,
        status=user_status,
        warehouse_id = warehouse_id
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        # Only a unique violation means "email is taken"; anything else
        # (e.g. a concurrent warehouse deletion) must not be reported as such
        if _pg_code(e) == UNIQUE_VIOLATION:
            raise EmailAlreadyExistsError(user_email) from e
        raise FailedToCreateUserError from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise FailedToCreateUserError from e
    
    await session.refresh(user, attribute_names=["role"])
    return user


async def update_user(
    session: AsyncSession,
    user: User,
    *,
    user_email: EmailStr | None = None,
    password: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    role_name: RoleName | None = None,
    user_status: UserStatus | None = None,
    warehouse_id: int | None | EllipsisType = ...,
) -> User:
    """
    Updates a user.

    ``warehouse_id`` uses ``...`` as a sentinel: ``None`` explicitly detaches
    the warehouse, ``...`` (the field was absent from the request) keeps it.
    """
    is_email_changed: bool = (
        user_email is not None and user_email != user.email
    )
    if is_email_changed:
        user_exist_stmt = (
            select(User.id)
            .where(
                User.email == user_email,
                User.id != user.id
            )
        )
        is_user_already_exists = await session.scalar(user_exist_stmt)
        if is_user_already_exists:
            raise EmailAlreadyExistsError(user_email)
        user.email = str(user_email)

    if password is not None:
        user.password_hash = hash_password(password)
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if user_status is not None:
        user.status = user_status

    is_role_changed: bool = (
        role_name is not None and
        (user.role is None or user.role.name != role_name)
    )
    # Role the user will have after this update — needed for the warehouse check
    resulting_role: RoleName | None = (
        role_name if is_role_changed
        else (user.role.name if user.role is not None else None)
    )
    if is_role_changed:
        role: Role | None = await get_role_by_name(session, role_name)
        if role is None:
            raise RoleNotFoundError(role_name.value)
        user.role_id = role.id

    is_warehouse_changed: bool = warehouse_id is not ...
    if is_warehouse_changed:
        await _ensure_warehouse_exists(session, warehouse_id)
        user.warehouse_id = warehouse_id

    # The invariant is checked only when this very request could break it,
    # so legacy storekeepers without a warehouse can still be renamed
    if (
        (is_warehouse_changed or is_role_changed)
        and resulting_role == RoleName.WORKER
        and user.warehouse_id is None
    ):
        raise WarehouseRequiredForStorekeeperError(
            "A storekeeper must be assigned to a warehouse"
        )

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if _pg_code(e) == UNIQUE_VIOLATION and user_email:
            raise EmailAlreadyExistsError(user_email) from e
        raise FailedToUpdateUserError from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise FailedToUpdateUserError from e
    
    await session.refresh(user)
    return user


async def _move_storekeepers_with_manager(
    session: AsyncSession,
    manager: User,
    new_warehouse_id: int | None,
) -> None:
    """Storekeepers follow their manager to the new warehouse.

    The cascade is allowed only while the manager is the sole active manager of
    the warehouse — otherwise we would take someone else's storekeepers away.
    When a safe move is impossible the reassignment is rejected instead of
    leaving storekeepers orphaned or detached from the warehouse.
    """
    old_warehouse_id: int | None = manager.warehouse_id
    if old_warehouse_id is None or old_warehouse_id == new_warehouse_id:
        return

    if await count_storekeepers(session, old_warehouse_id) == 0:
        return

    if new_warehouse_id is None:
        raise ManagerHasStorekeepersError(
            "The warehouse cannot be detached: it still has storekeepers assigned"
        )

    if await count_active_managers(session, old_warehouse_id, exclude_user_id=manager.id) > 0:
        raise ManagerHasStorekeepersError(
            "Another manager is responsible for this warehouse: move the storekeepers manually"
        )

    storekeeper_role: Role | None = await get_role_by_name(session, RoleName.WORKER)
    if storekeeper_role is None:
        raise RoleNotFoundError(RoleName.WORKER.value)

    await session.execute(
        update(User)
        .where(
            User.warehouse_id == old_warehouse_id,
            User.role_id == storekeeper_role.id,
        )
        .values(warehouse_id=new_warehouse_id)
    )


#функція для прив'язки складу до менджера складу або зняття 
async def assign_warehouse(
    session: AsyncSession,
    user_id: int,
    warehouse_id: int | None,
) -> User:
    #перевірка існування користувача
    user: User | None = await get_user(session, user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    
    #перевірка ролі користувача
    if user.role is None or user.role.name != RoleName.WAREHOUSE_MANAGER:
        raise UserIsNotManagerError(user_id)
    
    #перевірка існування складу
    if warehouse_id is not None:
        warehouse = await session.get(Warehouse, warehouse_id)
        
        if warehouse is None:
            raise WareHouseNotFoundError(warehouse_id)
        
    #комірники цього менеджера переїжджають разом з ним
    await _move_storekeepers_with_manager(session, user, warehouse_id)
    
    #оновлення занчення в пам'яті
    user.warehouse_id = warehouse_id
    
    try:
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback() 
        raise FailedToUpdateUserError from e
    
    await session.refresh(user)
    
    return user


async def delete_user(
    session: AsyncSession,
    user_id: int
) -> None:
    user: User | None = await get_user(
        session,
        user_id,
        options=[]
    )
    if user is None:
        raise UserNotFoundError(user_id)
    
    try:
        await session.delete(user)
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise UserCannotBeDeletedError(
            f"User with id {user_id} cannot be deleted due to related records."
        ) from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise FailedToDeleteUserError(
            f"Failed to delete user with id {user_id}."
        ) from e


async def count_active_admins(
    session: AsyncSession,
    exclude_user_id: int | None = None
) -> int:
    """
    Number of active root/administrators.
    To protect against system lockout.
    """
    conditions = [
        Role.name.in_([
            RoleName.ROOT,
            RoleName.ADMIN
        ]),
        User.status == UserStatus.ACTIVE,
    ]
    
    if exclude_user_id is not None:
        conditions.append(User.id != exclude_user_id)
    
    stmt = (
        select(func.count(User.id))
        .select_from(User)
        .join(User.role)
        .where(*conditions)
    )
    
    result: int = await session.scalar(stmt) or 0
    return result
