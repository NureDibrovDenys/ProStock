"""Матриця прав доступу за ролями.

Єдине місце, де описано, що дозволено кожній ролі. Використовується і для
перевірки на бекенді (`require_roles`), і для підказок фронтенду
(`GET /api/v1/auth/me` → `permissions`).
"""
from __future__ import annotations

from app.core.enums import RoleName

# ── Ролі ───────────────────────────────────────────────────────────────────

ALL_ROLES: frozenset[str] = frozenset(role.value for role in RoleName)

# Керівні ролі: повний доступ до довідників і користувачів
ADMIN_ROLES: frozenset[str] = frozenset(
    {
        RoleName.ROOT.value,
        RoleName.ADMIN.value,
    }
)

# Ролі, що можуть змінювати товари (створення / редагування / імпорт)
PRODUCT_WRITE_ROLES: frozenset[str] = ADMIN_ROLES | {RoleName.WAREHOUSE_MANAGER.value}

# Видалення товарів — лише керівні ролі
PRODUCT_DELETE_ROLES: frozenset[str] = ADMIN_ROLES

# Читання товарів — будь-який автентифікований користувач
PRODUCT_READ_ROLES: frozenset[str] = ALL_ROLES

# Керування обліковими записами — root та адміністратор
USER_MANAGE_ROLES: frozenset[str] = ADMIN_ROLES


def permissions_for(role: str) -> dict[str, bool]:
    """Повертає плоский список можливостей для ролі (для UI)."""
    return {
        "products_read": role in PRODUCT_READ_ROLES,
        "products_write": role in PRODUCT_WRITE_ROLES,
        "products_delete": role in PRODUCT_DELETE_ROLES,
        "products_import": role in PRODUCT_WRITE_ROLES,
        "products_export": role in PRODUCT_READ_ROLES,
        "users_manage": role in USER_MANAGE_ROLES,
        "warehouse_map_write": role in PRODUCT_WRITE_ROLES,
    }
