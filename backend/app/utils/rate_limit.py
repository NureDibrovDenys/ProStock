"""
A simple in-memory login attempts limiter.

Protects against password brute-forcing.

This is sufficient for a single uvicorn process;
for multiple workers, it should be replaced with Redis.
"""
from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict, deque

from app.core.config import settings


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        cleanup_threshold: int = 10_000
    ) -> None:
        self.max_attempts: int = max_attempts
        self.window_seconds: int = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._cleanup_counter: int = 0
        self._cleanup_threshold: int = cleanup_threshold
        
    def _remove_expired_attempts(self, key: str, now: float) -> deque[float]:
        """
        Removes attempts that fall outside the time window and returns the current queue.
        """
        attempts: deque[float] = self._attempts[key]
        cutoff_time: float = now - self.window_seconds
        
        while attempts and attempts[0] <= cutoff_time:
            attempts.popleft()
        return attempts

    async def _periodic_cleanup(self, now: float) -> None:
        """
        Removes empty decks to prevent memory leaks during attacks from multiple IPs.
        """
        self._cleanup_counter += 1
        if self._cleanup_counter >= self._cleanup_threshold:
            self._cleanup_counter = 0
            
            cutoff_time: float = now - self.window_seconds
            keys_to_delete: list[str] = [
                key for key, attempts in self._attempts.items()
                if not attempts or attempts[-1] <= cutoff_time
            ]
            for key in keys_to_delete:
                self._attempts.pop(key, None)

    async def check(self, key: str) -> int:
        """
        Returns the number of seconds until the next attempt.
        0 — you can try.
        """
        async with self._lock:
            now: float = time.monotonic()
            await self._periodic_cleanup(now)
            attempts: deque[float] = self._remove_expired_attempts(key, now)
            
            if len(attempts) < self.max_attempts:
                return 0
            return max(
                0,
                math.ceil(self.window_seconds - (now - attempts[0]))
            )

    async def register_failure(self, key: str) -> None:
        async with self._lock:
            now: float = time.monotonic()
            attempts: deque[float] = self._remove_expired_attempts(key, now)
            attempts.append(now)

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)
