import { request } from './client';
import type {
  DashboardStats,
  RackDetails,
  RackSummary,
  Shelf,
  ShelfInput,
  ShelfPatch,
  Warehouse,
  WarehouseInput,
  WarehouseMap,
} from './types';

/** GET /api/v1/warehouses/{id} */
export const getWarehouse = (warehouseId: number) => request<Warehouse>(`/warehouses/${warehouseId}`);

/** GET /api/v1/warehouses - усі склади (лише root / administrator). */
export const getWarehouses = () => request<Warehouse[]>('/warehouses');

/** POST /api/v1/warehouses - створення складу (лише root / administrator). */
export const createWarehouse = (data: WarehouseInput) => request<Warehouse>('/warehouses', { method: 'POST', body: data });

/** PATCH /api/v1/warehouses/{id} - зміна назви, адреси чи площі (лише root / administrator). */
export const updateWarehouse = (warehouseId: number, data: Partial<WarehouseInput>) =>
  request<Warehouse>(`/warehouses/${warehouseId}`, { method: 'PATCH', body: data });

/** GET /api/v1/warehouses/{id}/map */
export async function getWarehouseMap(warehouseId: number): Promise<WarehouseMap> {
  const data = await request<Partial<WarehouseMap>>(`/warehouses/${warehouseId}/map`);
  // Порожній склад може прийти без деяких масивів
  return {
    walls: data.walls ?? [],
    partitions: data.partitions ?? [],
    racks: data.racks ?? [],
    obstacles: data.obstacles ?? [],
    zones: data.zones ?? [],
    entry_points: data.entry_points ?? [],
  };
}

/** PUT /api/v1/warehouses/{id}/map - повністю замінює топологію складу. */
export const saveWarehouseMap = (warehouseId: number, map: WarehouseMap) =>
  request<WarehouseMap>(`/warehouses/${warehouseId}/map`, { method: 'PUT', body: map });

/** GET /api/v1/warehouses/{id}/dashboard */
export const getDashboard = (warehouseId: number) => request<DashboardStats>(`/warehouses/${warehouseId}/dashboard`);

/** GET /api/v1/warehouses/{id}/racks - коротка інформація та заповненість стелажів. */
export const getRacks = (warehouseId: number) => request<RackSummary[]>(`/warehouses/${warehouseId}/racks`);

/** GET /api/v1/warehouses/{id}/racks/{rack_code} - полиці стелажа. */
export const getRackDetails = (warehouseId: number, rackCode: string) =>
  request<RackDetails>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}`);

// ── Полиці ─────────────────────────────────────────────────────────────────

/** GET /api/v1/warehouses/{id}/racks/{rack_code}/shelves - повні дані полиць стелажа. */
export const listShelves = (warehouseId: number, rackCode: string) =>
  request<Shelf[]>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}/shelves`);

/** GET /api/v1/warehouses/{id}/racks/{rack_code}/shelves/{shelf_id} - повні дані полиці. */
export const getShelf = (warehouseId: number, rackCode: string, shelfId: number) =>
  request<Shelf>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}/shelves/${shelfId}`);

/** POST /api/v1/warehouses/{id}/racks/{rack_code}/shelves - створення полиці (адмін / менеджер). */
export const createShelf = (warehouseId: number, rackCode: string, data: ShelfInput) =>
  request<Shelf>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}/shelves`, {
    method: 'POST',
    body: data,
  });

/** PATCH /api/v1/warehouses/{id}/racks/{rack_code}/shelves/{shelf_id} - часткове оновлення (адмін / менеджер). */
export const updateShelf = (warehouseId: number, rackCode: string, shelfId: number, data: ShelfPatch) =>
  request<Shelf>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}/shelves/${shelfId}`, {
    method: 'PATCH',
    body: data,
  });

/** DELETE /api/v1/warehouses/{id}/racks/{rack_code}/shelves/{shelf_id} - видалення полиці (адмін / менеджер). */
export const deleteShelf = (warehouseId: number, rackCode: string, shelfId: number) =>
  request<void>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}/shelves/${shelfId}`, {
    method: 'DELETE',
  });
