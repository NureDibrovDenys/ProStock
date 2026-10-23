import { request } from './client';
import type { NewUser, RoleName, User } from './types';

/** GET /api/v1/users?warehouse_id={id} — співробітники складу. */
export const getUsers = (warehouseId: number) => request<User[]>('/users', { query: { warehouse_id: warehouseId } });

/** POST /api/v1/users — створення облікового запису. */
export const createUser = (data: NewUser) => request<User>('/users', { method: 'POST', body: data });

export const ROLE_LABELS: Record<RoleName, string> = {
  root: 'Root',
  administrator: 'Адміністратор',
  warehouse_manager: 'Менеджер складу',
  storekeeper: 'Комірник',
};
