"""Авторизація: вхід, оновлення токена, профіль, вихід."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.db import get_async_session
from app.core.enums import UserStatus
from app.core.rbac import permissions_for
from app.schemas import (
    AuthResponseSchema,
    ProfileSchema,
    UserLoginSchema,
)
from app.users.models import RefreshToken, User
from app.utils.rate_limit import login_rate_limiter
from app.utils.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_token,
    verify_password,
)

#роутер для аутентифікації
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

REFRESH_COOKIE_PATH = "/api/v1/auth"


# ── Допоміжні функції ──────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _profile(user: User) -> dict:
    role = user.role.name.value if user.role else "guest"
    return {
        "user_id": user.id,
        "user_email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": role,
        "status": user.status.value if hasattr(user.status, "value") else str(user.status),
        "permissions": permissions_for(role),
        "created_at": user.created_at,
    }


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        httponly=True,          # недоступний для JS → захист від XSS-крадіжки
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


async def _load_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.scalar(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )


async def _issue_session(
    session: AsyncSession,
    user: User,
    response: Response,
    request: Request,
) -> tuple[str, int]:
    """Видає access-токен і новий refresh-токен (cookie + хеш у БД)."""
    access_token, expires_in = create_access_token(
        subject=user.email,
        user_id=user.id,
        role=user.role.name.value if user.role else "guest",
    )
    raw_refresh, refresh_expires_at = create_refresh_token(user.id)

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=refresh_expires_at,
            user_agent=request.headers.get("user-agent"),
            ip=(request.client.host if request.client else None),
        )
    )
    await session.commit()
    _set_refresh_cookie(response, raw_refresh)
    return access_token, expires_in


# ── Ендпоінти ──────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponseSchema)
async def login(
    user_credentials: UserLoginSchema,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    """Вхід за email і паролем.

    Повертає короткоживучий access-токен у тілі відповіді та refresh-токен
    у httpOnly cookie (фронтенд не має до нього доступу з JS).
    """
    _no_store(response)

    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{user_credentials.email}|{client_ip}"
    retry_after = await login_rate_limiter.check(limiter_key)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Забагато спроб входу. Спробуйте через {retry_after} с.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await session.scalar(
        select(User)
        .options(selectinload(User.role))
        .where(User.email == user_credentials.email)
    )

    # Однакова відповідь для неіснуючого email і неправильного пароля
    if user is None or not verify_password(
        user_credentials.password, user.password_hash if user else None
    ):
        await login_rate_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Обліковий запис заблоковано або деактивовано",
        )

    await login_rate_limiter.reset(limiter_key)
    access_token, expires_in = await _issue_session(session, user, response, request)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": _profile(user),
    }


@router.post("/refresh", response_model=AuthResponseSchema)
async def refresh_access_token(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    """Оновлює access-токен за refresh-токеном із httpOnly cookie.

    Refresh-токен одноразовий: після успішного оновлення старий відкликається
    (rotation), що обмежує шкоду від його компрометації.
    """
    _no_store(response)

    raw_refresh = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сесія не знайдена. Увійдіть знову.",
        )

    try:
        payload = decode_token(raw_refresh, REFRESH_TOKEN_TYPE)
        user_id = int(payload.get("sub", ""))
    except (ValueError, TypeError) as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сесія прострочена. Увійдіть знову.",
        ) from exc

    stored = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(raw_refresh),
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > _now(),
        )
    )
    if stored is None:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сесія недійсна. Увійдіть знову.",
        )

    user = await _load_user(session, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        stored.revoked_at = _now()
        await session.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сесія недійсна. Увійдіть знову.",
        )

    # Ротація: старий токен більше не діє
    stored.revoked_at = _now()
    await session.flush()

    access_token, expires_in = await _issue_session(session, user, response, request)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": _profile(user),
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
    """Відкликає refresh-токен і чистить cookie."""
    raw_refresh = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw_refresh:
        stored = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(raw_refresh),
                RefreshToken.revoked_at.is_(None),
            )
        )
        if stored is not None:
            stored.revoked_at = _now()
            await session.commit()

    _clear_refresh_cookie(response)
    return {"detail": "Ви вийшли з системи"}


@router.get("/me", response_model=ProfileSchema)
async def current_user(
    response: Response,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Профіль поточного користувача з актуальною роллю та правами."""
    _no_store(response)
    user = await _load_user(session, current_user["id"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Користувача не знайдено",
        )
    profile = _profile(user)
    return profile
