"""
Security:
- password hashing;
- JWT tokens;
- session verification;
- access rights.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.db import get_async_session
from app.core.enums import RoleName, UserStatus
from app.core.rbac import ALL_ROLES, PRODUCT_WRITE_ROLES
from app.users.models import User

# Passwords

# bcrypt limitation: max 72 bytes of input data
MAX_PASSWORD_BYTES: int = 72

# Used when a user with the given email does not exist:
# the password check takes the same amount of time
# as it would for a real account
# (protection against brute-force attacks).
_DUMMY_HASH: str = bcrypt.hashpw(
    b"prostock-dummy-password",
    bcrypt.gensalt()
).decode()

# JWT

ALGORITHM: str = "HS256"
ACCESS_TOKEN_TYPE: str = "access"
REFRESH_TOKEN_TYPE: str = "refresh"

ACCESS_TOKEN_EXPIRE_MINUTES: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES

SECRET_KEY = settings.SECRET_KEY
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY not set. Add line SECRET_KEY=... to backend/.env file "
        "(generate: python -c \"import secrets; print(secrets.token_hex(32))\")"
    )

# Compatibility with legacy role names
ROOT: RoleName = RoleName.ROOT
ADMIN: RoleName = RoleName.ADMIN
WAREHOUSE_MANAGER: RoleName = RoleName.WAREHOUSE_MANAGER
STOREKEEPER: RoleName = RoleName.WORKER
GUEST: RoleName = RoleName.GUEST

bearer_scheme: HTTPBearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """
    Hashes the password using bcrypt with a check for the 72-byte limit.
    """
    raw: bytes = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("The password is too long (max 72 bytes")
    
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()

def verify_password(
    plain_password: str,
    hashed_password: str | None
) -> bool:
    """
    Verifies a password against a bcrypt hash.
    
    If the user is not found ('hashed_password is None'),
    a check is still performed against a dummy hash
    so that the response time does not reveal the existence of the account.
    """
    raw: bytes = plain_password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(
            raw,
            (hashed_password or _DUMMY_HASH).encode("utf-8")
        )
    except (ValueError, TypeError):
        # Corrupted hash in the DB
        return False

# Token generation

def _now() -> datetime:
    return datetime.now(timezone.utc)

def create_access_token(
    subject: str,
    user_id: int,
    role_name: RoleName | str,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """
    Creates an access token.
    Returns (token expires_in_seconds).
    """
    expires_delta = expires_delta or timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at: datetime = _now() + expires_delta
    
    role_value: str = (
        role_name.value if isinstance(role_name, RoleName) else str(role_name)
    )
    
    payload: dict[str, Any] = {
        "sub": subject,
        "uid": user_id,
        "role": role_value,
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return (
        jwt.encode(
            payload,
            SECRET_KEY,
            algorithm=ALGORITHM
        ),
        int(expires_delta.total_seconds())
    )

def create_refresh_token(
    user_id: int,
    expires_delta: timedelta | None = None
) -> tuple[str, datetime]:
    """
    Creates a refresh token.
    Returns (raw_token, expires_at).
    """
    expires_delta: timedelta | None = expires_delta or timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_at: datetime = _now() + expires_delta
    
    payload: dict[str, str | int] = {
        "sub": str(user_id),
        "type": REFRESH_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return (
        jwt.encode(
            payload,
            SECRET_KEY,
            algorithm=ALGORITHM
        ),
        expires_at
    )

def decode_token(
    raw_token: str,
    expected_type: str
) -> dict[str, Any]:
    """
    Decodes a JWT and verifies its type and signature.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            raw_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except JWTError as e:
        raise ValueError("Invalid or expired token") from e

    if payload.get("type") != expected_type:
        raise ValueError("Invalid token type")
    return payload

def hash_token(raw_token: str) -> str:
    """
    The SHA-256 hash of the refresh token is stored in the DB.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

# Current user

def _credentials_error(
    detail: str = "Unable to verify credentials"
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Verifies the access token and loads the user's current state from the DB.
    
    The role and status are retrieved from the DB,
    rather than solely from the token:
    a blocked user loses access immediately,
    even if their access token has not yet expired.
    """
    is_invalid_credentials: bool = (
        credentials is None
        or credentials.scheme.lower() != "bearer"
    )
    if is_invalid_credentials:
        raise _credentials_error()

    try:
        payload: dict[str, Any] = decode_token(
            credentials.credentials,
            ACCESS_TOKEN_TYPE
        )
    except ValueError as e:
        raise _credentials_error() from e

    user_id: str | Any | None = payload.get("uid")
    if not isinstance(user_id, int):
        raise _credentials_error()
    
    stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = await session.scalar(stmt)

    if user is None:
        raise _credentials_error()

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The account is blocked or deactivated.",
        )

    role_name: RoleName = user.role.name if user.role else GUEST
    if role_name not in ALL_ROLES:
        raise _credentials_error()

    return {
        "id": user.id,
        "email": user.email,
        "role": role_name.value,
        "status": user.status.value,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }

async def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    is_admin: bool = current_user["role"] in {
        ADMIN.value,
        ROOT.value
    }
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access rights required."
        )
    return current_user

def require_roles(
    *allowed_roles: RoleName | str
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """
    Dependency factory: allows only specified roles.
    """
    allowed: frozenset[str] = frozenset(
        role.value if isinstance(role, RoleName) else str(role)
        for role in allowed_roles
    )

    async def role_checker(
        current_user: dict[str, Any] = Depends(get_current_user)
    ) -> dict[str, Any]:
        is_user_role_allowed: bool = current_user["role"] in allowed
        if not is_user_role_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to perform this operation",
            )
        return current_user

    return role_checker


# Ready-made dependencies for routers
require_admin: Callable[
    ...,
    Coroutine[Any, Any, dict[str, Any]]
] = require_roles(ADMIN, ROOT)

require_product_write: Callable[
    ...,
    Coroutine[Any, Any, dict[str, Any]]
] = require_roles(*PRODUCT_WRITE_ROLES)
