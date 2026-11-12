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
from app.core.enums import RoleName

from app.users import crud
from app.users.models import User
from app.core.serializers import serialize_user
from app.users.schemas import (
    StorekeeperCreatePayload,
    StorekeeperUpdatePayload,
    UserListItem,
    UserListResponse,
)
from app.utils.security import (
    get_current_admin_user,
    get_current_user,

)

router = APIRouter(prefix="/api/v1/managers", tags = ["Managers"])


@router.post(
    "/storekeepers",
    response_model=UserListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a storekeeper",
    description=(
        "Available only to warehouse managers"
        "Creates a storekeeper assigned to the manager's warehouse."
        
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "User successfully created"
        },
        status.HTTP_409_CONFLICT: {
            "description": "A user with this email is already registered"
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Only warehouse managers with an assigned warehouse can create storekeepers"
        },
    } 
)
async def create_user(
    payload: StorekeeperCreatePayload,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListItem:
    
    #перевірка на авторизованого користувача
    if current_user["role"] != RoleName.WAREHOUSE_MANAGER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only warehouse managers can create storekeepers"
        )
        
    #перевіремо чи менеджеру призначено склад
    warehouse_id = current_user["warehouse_id"]
    if warehouse_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to any warehouse"
        )
    try:
        user: User = await crud.create_user(
            session,
            user_email=payload.user_email,
            password=payload.password,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            role_name=RoleName.WORKER,
            warehouse_id=warehouse_id
        )
    except crud.EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email is already registered",
        ) from e
    except crud.RoleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storekeeper role is not configured in the system",
        ) from e
    except crud.FailedToCreateUserError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create storekeeper",
        ) from e

    return UserListItem(
        user_id=user.id,
        user_email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.name,
        status=user.status,
        warehouse_id=user.warehouse_id,
        created_at=user.created_at,
    )


# ── Перегляд і редагування комірників свого складу ─────────────────────────

def _manager_warehouse_id(current_user: dict) -> int:
    """Склад поточного менеджера; 403 для інших ролей або менеджера без складу."""
    if current_user["role"] != RoleName.WAREHOUSE_MANAGER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only warehouse managers can manage storekeepers",
        )
    warehouse_id = current_user["warehouse_id"]
    if warehouse_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to any warehouse",
        )
    return warehouse_id


async def _get_own_storekeeper(session: AsyncSession, user_id: int, warehouse_id: int) -> User:
    """Комірник складу менеджера. Чужі та неіснуючі користувачі — однаково 404,
    щоб менеджер не міг дізнатися про облікові записи поза своїм складом."""
    user = await crud.get_user(session, user_id)
    if (
        user is None
        or user.role is None
        or user.role.name != RoleName.WORKER
        or user.warehouse_id != warehouse_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storekeeper not found",
        )
    return user


@router.get(
    "/storekeepers",
    response_model=UserListResponse,
    summary="List storekeepers of the manager's warehouse",
)
async def list_storekeepers(
    search: str | None = Query(None, max_length=100, description="Search by name or email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListResponse:
    warehouse_id = _manager_warehouse_id(current_user)
    users, total = await crud.list_users(
        session,
        search=search,
        role_name=RoleName.WORKER,
        warehouse_id=warehouse_id,
        page=page,
        page_size=page_size,
    )
    return UserListResponse(
        items=[serialize_user(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get(
    "/storekeepers/{user_id}",
    response_model=UserListItem,
    summary="Get a storekeeper of the manager's warehouse",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Storekeeper not found on your warehouse"}},
)
async def get_storekeeper(
    user_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListItem:
    warehouse_id = _manager_warehouse_id(current_user)
    user = await _get_own_storekeeper(session, user_id, warehouse_id)
    return serialize_user(user)


@router.patch(
    "/storekeepers/{user_id}",
    response_model=UserListItem,
    summary="Update a storekeeper of the manager's warehouse",
    description="A manager can change only first/last name, email and password of own storekeepers.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Storekeeper not found on your warehouse"},
        status.HTTP_409_CONFLICT: {"description": "A user with this email is already registered"},
    },
)
async def update_storekeeper(
    payload: StorekeeperUpdatePayload,
    user_id: int = Path(..., gt=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserListItem:
    warehouse_id = _manager_warehouse_id(current_user)
    user = await _get_own_storekeeper(session, user_id, warehouse_id)
    try:
        updated: User = await crud.update_user(
            session,
            user,
            user_email=payload.user_email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except crud.EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email is already registered",
        ) from e
    except crud.FailedToUpdateUserError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update storekeeper",
        ) from e
    return serialize_user(updated)
