import { useQuery } from '@tanstack/react-query';
import { getWarehouse } from '../api/warehouse';
import { useCurrentWarehouse } from './useCurrentWarehouse';

/** Назва поточного складу; поки бекенд не відповів — «№ id». */
export function useWarehouseName(): string {
  const warehouseId = useCurrentWarehouse();
  const query = useQuery({
    queryKey: ['warehouse', warehouseId],
    enabled: warehouseId != null,
    queryFn: () => {
      if (warehouseId === null) {
        throw new Error('Склад не призначено');
      }

      return getWarehouse(warehouseId);
    },
  });

  if (warehouseId === null){
    return 'Без складу';
  }
  
  return query.data?.warehouse_name ?? `№ ${warehouseId}`;
}
