import { request } from './client';
import type { DashboardStats, RackDetails, RackSummary, Warehouse, WarehouseMap } from './types';

/** GET /api/v1/warehouses/{id} */
export const getWarehouse = (warehouseId: number) => request<Warehouse>(`/warehouses/${warehouseId}`);

/** GET /api/v1/warehouses — доступні склади для прив'язки облікового запису. */
export const getWarehouses = () => request<Warehouse[]>('/warehouses');

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

/** PUT /api/v1/warehouses/{id}/map — повністю замінює топологію складу. */
export const saveWarehouseMap = (warehouseId: number, map: WarehouseMap) =>
  request<WarehouseMap>(`/warehouses/${warehouseId}/map`, { method: 'PUT', body: map });

/** GET /api/v1/warehouses/{id}/dashboard */
export const getDashboard = (warehouseId: number) => request<DashboardStats>(`/warehouses/${warehouseId}/dashboard`);

/** GET /api/v1/warehouses/{id}/racks — коротка інформація та заповненість стелажів. */
export const getRacks = (warehouseId: number) => request<RackSummary[]>(`/warehouses/${warehouseId}/racks`);

/** GET /api/v1/warehouses/{id}/racks/{rack_code} — полиці стелажа. */
export const getRackDetails = (warehouseId: number, rackCode: string) =>
  request<RackDetails>(`/warehouses/${warehouseId}/racks/${encodeURIComponent(rackCode)}`);
