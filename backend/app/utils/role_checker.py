from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from app.utils.security import get_current_user


class RoleChecker:
    """FastAPI dependency для перевірки доступу за роллю."""

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = frozenset(allowed_roles)

    async def __call__(
        self,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if current_user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостатньо прав для виконання цієї операції",
            )
        return current_user
