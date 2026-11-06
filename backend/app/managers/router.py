from __future__ import annotations
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
from app.users.schemas import (
    StorekeeperCreatePayload,
    UserListItem,

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
