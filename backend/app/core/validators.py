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
