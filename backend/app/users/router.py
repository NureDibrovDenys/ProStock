from __future__ import annotations

import math

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
    Path
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.enums import RoleName, UserStatus
from app.core.rbac import USER_MANAGE_ROLES
from app.core.serializers import serialize_user

from app.users import crud
from app.users.models import User
from app.users.schemas import (
    UserCreatePayload,
    UserListItem,
    UserListResponse,
    UserUpdatePayload,
)
from app.utils.security import (
    get_current_user,
    get_current_admin_user,
    require_roles
)

router: APIRouter = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
    dependencies=[
        Depends(
            require_roles(
                *USER_MANAGE_ROLES
            )
        )
    ],
)

COMMON_RESPONSES: dict[int, dict[str, str]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authorization required (token missing or invalid)"
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Insufficient access right (Admin or Root role required)"
    }
}

NOT_FOUND_RESPONSE: dict[int, dict[str, str]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "A user with this ID not found"
    }
}


def _to_item(user: User) -> UserListItem:
    return serialize_user(user)


@router.get(
    "",
    response_model=UserListResponse,
    summary="Retrieve a paginated list of users",
    description=(
        "Available only to admins. "
        "Allows searching by name or email, "
        "as well as filtering by role and status"
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "List of users successfully received"
        }
    } | COMMON_RESPONSES
)
async def list_users(
    search: str | None = Query(
        None,
        max_length=100,
        description="Case-insensitive search by name or email",
        example={
            "default": {
                "summary": "Search by part of a name",
                "value": "Alex"
            }
        },
    ),
    role: RoleName | None = Query(
        None,
        description="Filter by a specific user role"
    ),
    user_status: UserStatus | None = Query(
        None,
        alias="status",
        description="Filter by a user status"
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number for pagination"
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of users per page (max 100)"
    ),
    _: dict = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListResponse:
    users, total = await crud.list_users(
        session,
        search=search,
        role_name=role,
        user_status=user_status,
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


@router.post(
    "",
    response_model=UserListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description=(
        "Available only to admins. "
        "Creates a new user in the system "
        "with the specified role, status, and hashed password"
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "User successfully created"
        },
        status.HTTP_409_CONFLICT: {
            "description": "A user with this email is already registered"
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The specified role does not exists or the data failed validation"
        },
    } | COMMON_RESPONSES,
)
async def create_user(
    payload: UserCreatePayload,
    _: dict = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListItem:
    try:
        user: User = await crud.create_user(
            session,
            user_email=payload.user_email,
            password=payload.password,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            role_name=payload.role,
            user_status=payload.status,
        )
    except crud.EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email is already registered",
        ) from e
    except crud.RoleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The specified role does not exists",
        ) from e

    return _to_item(user)


@router.get(
    "/{user_id}",
    response_model=UserListItem,
    summary="Retrieve user information by ID",
    description=(
        "Available only to admins. "
        "Returns detailed information about a specific user."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "User successfully retrieved"
        },
    } | COMMON_RESPONSES | NOT_FOUND_RESPONSE,
)
async def get_user(
    user_id: int = Path(
        ...,
        gt=0,
        description="Unique user identifier",
        example={
            "default": {
                "summary": "User ID",
                "value": 1
            }
        },
    ),
    _: dict = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListItem:
    user: User | None = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A user with this ID not found")
    return _to_item(user)


@router.patch(
    "/{user_id}",
    response_model=UserListItem,
    summary="Update user information by ID",
    description=(
        "Allows updating user information. "
        "Admins can edit anyone; "
        "regular users can only edit their own profile."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "User successfully updated"
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflict (forbidden action)"
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The specified role does not exist, or validation error."
        }
    } | COMMON_RESPONSES | NOT_FOUND_RESPONSE,
)
async def update_user(
    user_id: int = Path(
        ...,
        gt=0,
        description="Unique user identifier",
        example={
            "default": {
                "summary": "User ID",
                "value": 1
            }
        },
    ),
    payload: UserUpdatePayload = ...,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListItem:
    is_admin: bool = current_user["role"] in {
        RoleName.ROOT.value,
        RoleName.ADMIN.value
    }
    is_self: bool = current_user["id"] == user_id
    
    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to edit another user's profile"
        )
    
    if not is_admin and payload.role is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to change user roles"
        )
    
    user: User | None = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A user with this ID not found"
        )

    removes_admin_rights: bool = (
        (
            payload.role is not None
            and payload.role not in {
                RoleName.ROOT,
                RoleName.ADMIN
            }
        ) or (
            payload.status is not None
            and payload.status != UserStatus.ACTIVE
        )
    )
    is_currently_admin: bool = (
        user.role is not None
        and user.role.name in {
            RoleName.ROOT,
            RoleName.ADMIN
        }
    )
    
    if removes_admin_rights and is_currently_admin:
        remaining_admins: int = await crud.count_active_admins(
            session,
            exclude_user_id=user.id
        )
        if remaining_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active admin cannot be stripped of their rights",
            )
    
    is_self_deactivate: bool = (
        user.id == current_user["id"]
        and payload.status is not None
        and payload.status != UserStatus.ACTIVE
    )
    
    if is_self_deactivate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account",
        )

    try:
        updated: User = await crud.update_user(
            session,
            user,
            user_email=payload.user_email,
            password=payload.password,
            first_name=payload.first_name.strip() if payload.first_name else None,
            last_name=payload.last_name.strip() if payload.last_name else None,
            role_name=payload.role,
            user_status=payload.status,
        )
    except crud.EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from e
    except crud.RoleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Specified role does not exist",
        ) from e

    return _to_item(updated)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a user's profile",
    description=(
        "Available only to admins. "
        "Removes a user from the system. "
        "It is not possible to delete your own account "
        "or the last active admin."
    ),
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "The user has been removed"
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflict (forbidden action)"
        }
    } | COMMON_RESPONSES | NOT_FOUND_RESPONSE,
)
async def delete_user(
    user_id: int = Path(
        ...,
        gt=0,
        description="Unique user identifier",
        example={
            "default": {
                "summary": "User ID",
                "value": 1
            }
        },
    ),
    _: dict = Depends(get_current_admin_user),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    user: User | None = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A user with this ID not found",
        )

    if user.id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot delete your own account",
        )

    is_admin: bool = (
        user.role is not None
        and user.role.name in {
            RoleName.ROOT,
            RoleName.ADMIN
        }
    )
    remaining_admins: int = await crud.count_active_admins(
        session,
        exclude_user_id=user.id
    )
    if is_admin and remaining_admins == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active admin cannot be removed",
        )

    try:
        await crud.delete_user(session, user_id)
    except crud.UserCannotBeDeletedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The user cannot be deleted due to associated records in the system",
        ) from e
    except crud.FailedToDeleteUserError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error when deleting a user",
        ) from e
    
    return None
