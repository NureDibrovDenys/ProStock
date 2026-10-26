"""Простий in-memory обмежувач спроб входу.

Захищає від перебору пароля. Для одного процесу uvicorn цього достатньо;
для кількох воркерів варто замінити на Redis (див. TODO).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from app.core.config import settings


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts[key]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        return attempts

    async def check(self, key: str) -> int:
        """Повертає кількість секунд до наступної спроби (0 — можна пробувати)."""
        async with self._lock:
            now = time.monotonic()
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return 0
            return max(1, int(self.window_seconds - (now - attempts[0])) + 1)

    async def register_failure(self, key: str) -> None:
        async with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)
