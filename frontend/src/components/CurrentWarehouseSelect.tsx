import { ChevronDown, Warehouse } from 'lucide-react';
import { selectWarehouse, useCurrentWarehouse, useWarehouses } from '../hooks/useCurrentWarehouse';
import styles from './NavBar.module.css';

/** Перемикач поточного складу в навбарі адміністратора: від нього залежать мапа, співробітники й дашборд. */
export function CurrentWarehouseSelect() {
  const warehouses = useWarehouses();
  const currentId = useCurrentWarehouse();
  const list = warehouses.data ?? [];

  return (
    <label className={styles.switcher} title="Поточний склад">
      <Warehouse size={16} aria-hidden />
      <select
        className={styles.switcherSelect}
        aria-label="Поточний склад"
        value={currentId ?? ''}
        onChange={(event) => selectWarehouse(Number(event.target.value))}
        disabled={list.length === 0}
      >
        {list.length === 0 && (
          <option value="">
            {warehouses.isPending ? 'Завантаження…' : warehouses.isError ? 'Склади недоступні' : 'Складів немає'}
          </option>
        )}
        {list.map((warehouse) => (
          <option key={warehouse.warehouse_id} value={warehouse.warehouse_id}>
            {warehouse.warehouse_name}
          </option>
        ))}
      </select>
      <ChevronDown size={16} className={styles.switcherChevron} aria-hidden />
    </label>
  );
}
