import { request } from './client';
import type { NewStorekeeper, NewUser, RoleName, User, UserList, UserStatus } from './types';

/** GET /api/v1/users — сторінка співробітників. */
export const getUsers = (params: { page?: number; page_size?: number; search?: string; role?: RoleName; warehouse_id?: number } = {}) =>
  request<UserList>('/users', {
    query: {
      page: params.page,
      page_size: params.page_size,
      search: params.search,
      role: params.role,
      warehouse_id: params.warehouse_id,
    },
  });

/** POST /api/v1/users — створення облікового запису. */
export const createUser = (data: NewUser) => request<User>('/users', { method: 'POST', body: data });

/** POST /api/v1/managers/storekeepers — менеджер створює комірника свого складу. */
export const createStorekeeper = (data: NewStorekeeper) =>
  request<User>('/managers/storekeepers', { method: 'POST', body: data });

/** PATCH /api/v1/users/{id} */
export const updateUser = (userId: number, data: Partial<NewUser> & { status?: UserStatus }) =>
  request<User>(`/users/${userId}`, { method: 'PATCH', body: data });

/** DELETE /api/v1/users/{id} */
export const deleteUser = (userId: number) => request<void>(`/users/${userId}`, { method: 'DELETE' });

export const ROLE_LABELS: Record<RoleName | 'guest', string> = {
  root: 'Root',
  administrator: 'Адміністратор',
  warehouse_manager: 'Менеджер складу',
  storekeeper: 'Комірник',
  guest: 'Гість',
};
