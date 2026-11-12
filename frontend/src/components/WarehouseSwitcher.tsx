import { useQuery } from '@tanstack/react-query';
import { Building2 } from 'lucide-react';
import { getWarehouses } from '../api/warehouse';
import { useAuth } from '../auth/AuthContext';
import { useSelectedWarehouse, setSelectedWarehouse } from '../hooks/useWarehouseSelection';
import { canSwitchWarehouse } from '../lib/roles';
import { cx } from '../lib/cx';
import styles from './WarehouseSwitcher.module.css';

/**
 * Перемикач поточного складу для адміністратора.
 *
 * Вибір одразу змінює `useCurrentWarehouse()`, тому мапа, дашборд і список
 * співробітників перемикаються без перезавантаження сторінки.
 * `variant="bar"` — у навігаційній панелі (темне тло), `variant="page"` — на світлій поверхні.
 */
export function WarehouseSwitcher({ variant = 'bar' }: { variant?: 'bar' | 'page' }) {
  const { session } = useAuth();
  const selected = useSelectedWarehouse();
  const allowed = canSwitchWarehouse(session?.user);
  // queryKey збігається з іншими екранами — список складів завантажується один раз
  const query = useQuery({
    queryKey: ['warehouses'],
    queryFn: getWarehouses,
    enabled: allowed,
  });

  if (!allowed) return null;

  const warehouses = query.data ?? [];
  // Адміністратору може бути призначено склад у профілі — показуємо його як поточний
  const current = selected ?? session?.user.warehouse_id ?? null;
  const placeholder = query.isPending
    ? 'Завантаження…'
    : query.isError
      ? 'Склади недоступні'
      : warehouses.length === 0
        ? 'Складів немає'
        : 'Оберіть склад';

  return (
    <label className={cx(styles.field, variant === 'page' && styles.pageField)}>
      <span className={styles.label}>
        <Building2 size={16} aria-hidden />
        Поточний склад
      </span>
      <select
        className={cx(styles.select, variant === 'page' && styles.pageSelect)}
        value={current === null ? '' : String(current)}
        disabled={query.isPending || query.isError || warehouses.length === 0}
        onChange={(event) => {
          const value = event.target.value;
          setSelectedWarehouse(value === '' ? null : Number(value));
        }}
      >
        <option value="">{placeholder}</option>
        {warehouses.map((warehouse) => (
          <option key={warehouse.warehouse_id} value={String(warehouse.warehouse_id)}>
            {warehouse.warehouse_name}
          </option>
        ))}
      </select>
    </label>
  );
}
