"""
Access rights matrix by role.

A single source of truth defining the permissions for each role.
It is used both for backend validation ('require_roles')
    and to provide hints to the frontend ('GET /api/v1/auth/me' ==> permissions)
"""
from __future__ import annotations

from app.core.enums import RoleName

# Roles (Enum objects for better typing)

ALL_ROLES: frozenset[RoleName] = frozenset(role for role in RoleName)

# Management roles: full access to directories and users
ADMIN_ROLES: frozenset[RoleName] = frozenset({
        RoleName.ROOT,
        RoleName.ADMIN,
})

# Roles that can modify products (creation/editing/import)
PRODUCT_WRITE_ROLES: frozenset[RoleName] = ADMIN_ROLES | {RoleName.WAREHOUSE_MANAGER}

# Deleting product — management roles only
PRODUCT_DELETE_ROLES: frozenset[RoleName] = ADMIN_ROLES

# Reading products — any authenticated user
PRODUCT_READ_ROLES: frozenset[RoleName] = ALL_ROLES

# Account management — root and admin
USER_MANAGE_ROLES: frozenset[RoleName] = ADMIN_ROLES

def permissions_for(role_name: RoleName | str) -> dict[str, bool]:
    """
    Return a list of capabilities for a role (for the UI).
    
    Supports both a RoleName object and a string (for DB compatibility).
    """
    
    # If the role is unknown to the system, return zero permissions
    try:
        role_enum: RoleName = RoleName(role_name)
    except ValueError:
        return {
            "products_read": False,
            "products_write": False,
            "products_delete": False,
            "products_import": False,
            "products_export": False,
            "users_manage": False,
            "warehouse_map_write": False,
        }
    
    return {
        "products_read": role_enum in PRODUCT_READ_ROLES,
        "products_write": role_enum in PRODUCT_WRITE_ROLES,
        "products_delete": role_enum in PRODUCT_DELETE_ROLES,
        "products_import": role_enum in PRODUCT_WRITE_ROLES,
        "products_export": role_enum in PRODUCT_READ_ROLES,
        "users_manage": role_enum in USER_MANAGE_ROLES,
        "warehouse_map_write": role_enum in PRODUCT_WRITE_ROLES,
    }
