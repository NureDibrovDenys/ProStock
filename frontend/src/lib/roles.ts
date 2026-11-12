import type { AuthUser } from '../api/types';

/** Адміністративні ролі — дзеркало ADMIN_ROLES з backend/app/core/rbac.py. */
const ADMIN_ROLES: ReadonlySet<AuthUser['role']> = new Set<AuthUser['role']>(['root', 'administrator']);

export function isAdminRole(role: AuthUser['role'] | undefined): boolean {
  return role !== undefined && ADMIN_ROLES.has(role);
}

/**
 * Чи може користувач перемикати поточний склад.
 *
 * Менеджер і комірник прив'язані до одного складу з профілю, тому перемикач їм не потрібен.
 * Адміністратор бачить усі склади; список складів (`GET /warehouses`) теж доступний лише йому.
 */
export function canSwitchWarehouse(user: AuthUser | null | undefined): boolean {
  return isAdminRole(user?.role);
}
