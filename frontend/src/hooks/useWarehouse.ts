import { useQuery } from '@tanstack/react-query';
import { getWarehouse } from '../api/warehouse';
import { WAREHOUSE_ID } from '../config';

/** Назва поточного складу; поки бекенд не відповів — «№ id». */
export function useWarehouseName(): string {
  const query = useQuery({ queryKey: ['warehouse', WAREHOUSE_ID], queryFn: () => getWarehouse(WAREHOUSE_ID) });
  return query.data?.warehouse_name ?? `№ ${WAREHOUSE_ID}`;
}
