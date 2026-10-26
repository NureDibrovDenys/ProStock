"""Безпека: хешування паролів, JWT-токени, перевірка сесії та прав доступу."""
from __future__ import annotations

import hashlib
import uuid
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
from app.core.rbac import ALL_ROLES, ADMIN_ROLES, PRODUCT_WRITE_ROLES
from app.users.models import User

# ── Паролі ─────────────────────────────────────────────────────────────────

# Обмеження bcrypt: максимум 72 байти вхідних даних
MAX_PASSWORD_BYTES = 72
# Використовується, коли користувача з таким email не існує: перевірка пароля
# займає стільки ж часу, скільки й для реального акаунта (захист від перебору).
_DUMMY_HASH = bcrypt.hashpw(b"prostock-dummy-password", bcrypt.gensalt()).decode()

# ── JWT ────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

SECRET_KEY = settings.SECRET_KEY
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY не задано. Додайте рядок SECRET_KEY=... у файл backend/.env "
        "(згенерувати: python -c \"import secrets; print(secrets.token_hex(32))\")"
    )

# Сумісність зі старими назвами ролей
ROOT = RoleName.ROOT.value
ADMIN = RoleName.ADMIN.value
WAREHOUSE_MANAGER = RoleName.WAREHOUSE_MANAGER.value
STOREKEEPER = RoleName.WORKER.value
GUEST = RoleName.GUEST.value

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Хешує пароль через bcrypt (з перевіркою 72-байтового ліміту)."""
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Пароль занадто довгий (максимум 72 байти)")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Перевіряє пароль проти bcrypt-хеша.

    Якщо користувача не знайдено (`hashed_password is None`) — усе одно
    виконується перевірка проти фіктивного хеша, щоб час відповіді не
    дозволяв визначати існування акаунта.
    """
    raw = plain_password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, (hashed_password or _DUMMY_HASH).encode("utf-8"))
    except (ValueError, TypeError):
        # Пошкоджений хеш у БД
        return False


# ── Генерація токенів ──────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str,
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """Створює access-токен. Повертає (token, expires_in_seconds)."""
    expires_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = _now() + expires_delta
    payload = {
        "sub": subject,
        "uid": user_id,
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), int(expires_delta.total_seconds())


def create_refresh_token(user_id: int, expires_delta: timedelta | None = None) -> tuple[str, datetime]:
    """Створює refresh-токен. Повертає (raw_token, expires_at)."""
    expires_delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_at = _now() + expires_delta
    payload = {
        "sub": str(user_id),
        "type": REFRESH_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), expires_at


def decode_token(raw_token: str, expected_type: str) -> dict[str, Any]:
    """Декодує JWT і перевіряє його тип та підпис."""
    try:
        payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Некоректний або прострочений токен") from exc

    if payload.get("type") != expected_type:
        raise ValueError("Невірний тип токена")
    return payload


def hash_token(raw_token: str) -> str:
    """SHA-256 від refresh-токена — саме це зберігається в БД."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ── Поточний користувач ────────────────────────────────────────────────────

def _credentials_error(detail: str = "Не вдалося перевірити облікові дані") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Перевіряє access-токен і завантажує актуальний стан користувача з БД.

    Роль і статус беруться з БД, а не лише з токена: заблокований користувач
    втрачає доступ негайно, навіть якщо його access-токен ще не прострочений.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_error()

    try:
        payload = decode_token(credentials.credentials, ACCESS_TOKEN_TYPE)
    except ValueError as exc:
        raise _credentials_error() from exc

    user_id = payload.get("uid")
    if not isinstance(user_id, int):
        raise _credentials_error()

    user = await session.scalar(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    if user is None:
        raise _credentials_error()

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Обліковий запис заблоковано або деактивовано",
        )

    role = user.role.name.value if user.role else GUEST
    if role not in ALL_ROLES:
        raise _credentials_error()

    return {
        "id": user.id,
        "email": user.email,
        "role": role,
        "status": user.status.value,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def require_roles(*allowed_roles: str):
    """Фабрика залежностей: пропускає лише вказані ролі."""
    allowed = frozenset(allowed_roles)

    async def role_checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if current_user["role"] not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостатньо прав для виконання цієї операції",
            )
        return current_user

    return role_checker


# Готові залежності для роутерів
require_admin = require_roles(*ADMIN_ROLES)
require_product_write = require_roles(*PRODUCT_WRITE_ROLES)
