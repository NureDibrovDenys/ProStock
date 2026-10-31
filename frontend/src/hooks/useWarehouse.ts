import { useQuery } from '@tanstack/react-query';
import { getWarehouse } from '../api/warehouse';
import { useCurrentWarehouse } from './useCurrentWarehouse';

/** Назва поточного складу; поки бекенд не відповів — «№ id». */
export function useWarehouseName(): string {
  const warehouseId = useCurrentWarehouse();
  const query = useQuery({ queryKey: ['warehouse', warehouseId], queryFn: () => getWarehouse(warehouseId) });
  return query.data?.warehouse_name ?? `№ ${warehouseId}`;
}
