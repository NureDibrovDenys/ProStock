import re
from typing import Any

# Allowed domains
PUBLIC_DOMAINS: set[str] = {
    "gmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "hotmail.com",
}

# Prohibited domains (e.g. spam)
BANNED_DOMAINS: set[str] | None = {
    "tempmail.com",
    "maximail.vip",
    "freeml.net",
}

# Email format validation (for a quick 422 response, without DNS checks)
EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
"""Спільні валідатори для SQLAlchemy ORM-моделей.

Централізована реалізація позбавляє від дублювання `_validate_positive_decimal`
у кожній моделі (WarehouseGrid, WarehouseObstacle, Zone, Rack, Shelf, Product…).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def validate_positive_decimal(key: str, value: object) -> Decimal:
    """Перевіряє, що значення є додатним числом, і повертає ``Decimal``.

    Призначений для використання в SQLAlchemy ``@validates`` обробниках:

        @validates("width")
        def validate_width(self, key, value):
            return validate_positive_decimal(key, value)

    Args:
        key: Ім'я атрибута (для повідомлення про помилку).
        value: Вхідне значення (може бути int, float, str або Decimal).

    Returns:
        ``Decimal`` > 0.

    Raises:
        ``ValueError`` якщо значення None, не числове, або ≤ 0.
    """
    if value is None:
        raise ValueError(f"Атрибут {key!r} не може бути None")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"Атрибут {key!r} має бути числом (отримано: {value!r})"
        )

    if decimal_value <= 0:
        raise ValueError(
            f"Атрибут {key!r} має бути додатним (отримано: {value!r})"
        )

    return decimal_value


def validate_non_negative_decimal(key: str, value: object) -> Decimal | None:
    """Перевіряє, що значення є невід'ємним числом або ``None``.

    Призначений для необов'язкових полів на кшталт ``min_stock_level``,
    ``max_capacity_m3`` тощо.

    Returns:
        ``Decimal`` >= 0 або ``None``.

    Raises:
        ``ValueError`` якщо значення не числове, або від'ємне.
    """
    if value is None:
        return None

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"Атрибут {key!r} має бути числом (отримано: {value!r})"
        )

    if decimal_value < 0:
        raise ValueError(
            f"Атрибут {key!r} не може бути від'ємним (отримано: {value!r})"
        )

    return decimal_value


def validate_rotation_angle(key: str, value: object) -> Decimal:
    """Перевіряє кут повороту: [0, 360).

    Returns:
        ``Decimal`` у діапазоні [0, 360).

    Raises:
        ``ValueError`` якщо значення виходить за межі.
    """
    if value is None:
        raise ValueError(f"Атрибут {key!r} не може бути None")

    try:
        angle = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"Атрибут {key!r} має бути числом (отримано: {value!r})"
        )

    if angle < 0 or angle >= 360:
        raise ValueError(
            f"Атрибут {key!r} має бути в діапазоні [0, 360) (отримано: {value!r})"
        )

    return angle

def normalize_and_validate_email(value: str) -> str:
    """
    Normalize email address:
    - converts the email to lowercase.

    Email validity check:
    - length (must be <= 255 characters);
    - by EMAIL_PATTERN;
    - local part length (must be <= 64 characters);
    - by BANNED_DOMAINS;
    - by EMAIL_PATTERN;
    - domain validity check
    """
    if not isinstance(value, str):
        raise ValueError(f"Email must be a string")
    
    value = value.strip().lower()
    
    if len(value) > 255:
        raise ValueError(f"Email must be at most 255 characters long")
    
    if not EMAIL_PATTERN.match(value):
        raise ValueError("Invalid email address")
    
    local_part, domain = value.rsplit("@", 1)
    
    if len(local_part) > 64:
        raise ValueError("Email local part (before '@' too long")
    
    if domain in BANNED_DOMAINS:
        raise ValueError("This email address is temporary or blocked")
    
    if domain not in PUBLIC_DOMAINS:
        if "." not in domain:
            raise ValueError("Invalid domain format")
        
        tld = domain.rsplit(".", 1)[-1]
        if len(tld) < 2:
            raise ValueError("The zone of the domain is incorrect")
    
    return value

def trim_names(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty or contain only spaces")
    return value