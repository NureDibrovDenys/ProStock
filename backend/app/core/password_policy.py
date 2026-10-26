"""Єдині правила перевірки пароля (використовуються API та створенням користувачів)."""
from __future__ import annotations

import re

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_PASSWORD_BYTES = 72  # обмеження bcrypt


def validate_password_strength(value: str) -> str:
    """Перевіряє складність пароля й повертає його без змін."""
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Пароль має містити щонайменше {MIN_PASSWORD_LENGTH} символів")
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Пароль має містити не більше {MAX_PASSWORD_LENGTH} символів")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Пароль занадто довгий (максимум 72 байти)")
    if not re.search(r"[A-ZА-ЯЇІЄҐ]", value):
        raise ValueError("Пароль має містити хоча б одну велику літеру")
    if not re.search(r"[a-zа-яїієґ]", value):
        raise ValueError("Пароль має містити хоча б одну малу літеру")
    if not re.search(r"\d", value):
        raise ValueError("Пароль має містити хоча б одну цифру")
    return value
