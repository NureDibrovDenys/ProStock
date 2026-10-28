from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from collections.abc import Sequence
from sqlalchemy.orm.interfaces import LoaderOption

from app.core.enums import RoleName, UserStatus
from app.users.models import Role, User
from app.utils.security import hash_password

from pydantic import EmailStr


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
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """Returns a page of users and the total number of users."""
    
    conditions: list = []
    
    if search and search.strip():
        pattern: str = f"%{search.strip()}%"
        conditions.append(
            or_(
                User.email.like(pattern),
                User.first_name.like(pattern),
                User.last_name.like(pattern),
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

    user: User = User(
        email=user_email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role_id=role.id,
        status=user_status,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise EmailAlreadyExistsError(user_email) from e
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
) -> User:
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
    if is_role_changed:
        role: Role | None = await get_role_by_name(session, role_name)
        if role is None:
            raise RoleNotFoundError(role_name.value)
        user.role_id = role.id
        user.role = role

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if user_email:
            raise EmailAlreadyExistsError(user_email) from e
        raise FailedToUpdateUserError from e
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
