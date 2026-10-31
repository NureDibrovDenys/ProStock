"""REST-ендпоінти для керування користувачами (лише root / адміністратор)."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import RoleName, UserStatus
from app.core.rbac import USER_MANAGE_ROLES
from app.users import crud
from app.users.models import User
from app.users.schemas import (
    UserCreatePayload,
    UserListItem,
    UserListResponse,
    UserUpdatePayload,
    serialize_user,
)
from app.utils.security import get_current_user, require_roles

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
    dependencies=[Depends(require_roles(*USER_MANAGE_ROLES))],
)


def _to_item(user: User) -> UserListItem:
    return serialize_user(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    search: str | None = Query(None, max_length=100, description="Пошук за ім'ям або email"),
    role: RoleName | None = Query(None, description="Фільтр за роллю"),
    user_status: UserStatus | None = Query(None, alias="status", description="Фільтр за статусом"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    warehouse_id: int | None = Query(None, gt=0, description="Фільтр за складом"),
    session: AsyncSession = Depends(get_async_session),
):
    users, total = await crud.list_users(
        session,
        search=search,
        role=role,
        status=user_status,
        warehouse_id=warehouse_id,
        page=page,
        page_size=page_size,
    )
    return UserListResponse(
        items=[_to_item(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreatePayload,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user = await crud.create_user(
            session,
            email=payload.user_email,
            password=payload.password,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            role=payload.role,
            status=payload.status,
            warehouse_id=payload.warehouse_id,
        )
    except crud.EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Користувач з такою поштою вже існує",
        ) from exc
    except crud.RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Вказаної ролі не існує",
        ) from exc

    return _to_item(user)


@router.get("/{user_id}", response_model=UserListItem)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    user = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")
    return _to_item(user)


@router.patch("/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: int,
    payload: UserUpdatePayload,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    user = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")

    removes_admin_rights = (
        (payload.role is not None and payload.role not in {RoleName.ROOT, RoleName.ADMIN})
        or (payload.status is not None and payload.status != UserStatus.ACTIVE)
    )
    is_currently_admin = user.role is not None and user.role.name in {RoleName.ROOT, RoleName.ADMIN}
    if removes_admin_rights and is_currently_admin:
        remaining = await crud.count_active_admins(session, exclude_user_id=user.id)
        if remaining == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Не можна позбавити прав останнього активного адміністратора",
            )

    if user.id == current_user["id"] and payload.status is not None and payload.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не можна деактивувати власний обліковий запис",
        )

    # warehouse_id: передаємо sentinel ..., якщо поле не було у запиті
    wh_sentinel = payload.warehouse_id if payload.warehouse_id is not None else ...

    try:
        updated = await crud.update_user(
            session,
            user,
            email=payload.user_email,
            password=payload.password,
            first_name=payload.first_name.strip() if payload.first_name else None,
            last_name=payload.last_name.strip() if payload.last_name else None,
            role=payload.role,
            status=payload.status,
            warehouse_id=wh_sentinel,
        )
    except crud.EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Користувач з такою поштою вже існує",
        ) from exc
    except crud.RoleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Вказаної ролі не існує",
        ) from exc

    return _to_item(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    user = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")

    if user.id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не можна видалити власний обліковий запис",
        )

    is_admin = user.role is not None and user.role.name in {RoleName.ROOT, RoleName.ADMIN}
    if is_admin and await crud.count_active_admins(session, exclude_user_id=user.id) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не можна видалити останнього активного адміністратора",
        )

    await crud.delete_user(session, user)
    return None
