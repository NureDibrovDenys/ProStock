import { Building2, Check, MapPin, Pencil, Ruler } from 'lucide-react';
import { useState } from 'react';
import type { Warehouse } from '../api/types';
import { Button } from '../components/Button';
import { WarehouseFormModal } from '../components/WarehouseFormModal';
import { ErrorState, LoadingState, PageHeader } from '../components/ui';
import { selectWarehouse, useCurrentWarehouse, useWarehouses } from '../hooks/useCurrentWarehouse';
import { formatNumber, plural } from '../lib/format';
import styles from './WarehousesPage.module.css';

/** Склади (лише root / administrator): список, створення, редагування й вибір поточного. */
export function WarehousesPage() {
  const query = useWarehouses();
  const currentId = useCurrentWarehouse();
  // undefined — форма закрита, null — новий склад, Warehouse — редагування
  const [editing, setEditing] = useState<Warehouse | null | undefined>(undefined);
  const warehouses = query.data ?? [];

  return (
    <>
      <PageHeader
        title="Склади"
        subtitle={
          query.data
            ? `${warehouses.length} ${plural(warehouses.length, ['склад', 'склади', 'складів'])} · поточний обирається в навбарі або тут`
            : undefined
        }
        actions={<Button onClick={() => setEditing(null)}>+ Новий склад</Button>}
      />

      {query.isPending && <LoadingState label="Завантаження складів…" />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data && warehouses.length === 0 && (
        <div className={styles.empty}>
          <Building2 size={40} aria-hidden />
          <p className={styles.emptyTitle}>Складів ще немає</p>
          <p className={styles.muted}>
            Створіть перший склад — після цього можна намалювати його мапу та призначити менеджера.
          </p>
          <Button onClick={() => setEditing(null)}>+ Створити склад</Button>
        </div>
      )}

      {warehouses.length > 0 && (
        <ul className={styles.grid}>
          {warehouses.map((w) => {
            const isCurrent = w.warehouse_id === currentId;
            return (
              <li key={w.warehouse_id} className={styles.card} data-current={isCurrent || undefined}>
                <div className={styles.cardHead}>
                  <h2 className={styles.name}>{w.warehouse_name}</h2>
                  {isCurrent && (
                    <span className={styles.badge}>
                      <Check size={14} aria-hidden /> Поточний
                    </span>
                  )}
                </div>
                <p className={styles.meta}>
                  <MapPin size={15} aria-hidden />
                  {w.warehouse_address ?? <span className={styles.muted}>Адресу не вказано</span>}
                </p>
                <p className={styles.meta}>
                  <Ruler size={15} aria-hidden />
                  {formatNumber(Number(w.total_warehouse_area))} м²
                </p>
                <div className={styles.actions}>
                  <Button variant="secondary" className={styles.action} onClick={() => setEditing(w)}>
                    <Pencil size={15} aria-hidden /> Редагувати
                  </Button>
                  {!isCurrent && (
                    <Button
                      variant="secondary"
                      className={styles.action}
                      onClick={() => selectWarehouse(w.warehouse_id)}
                    >
                      Зробити поточним
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {editing !== undefined && (
        <WarehouseFormModal
          warehouse={editing ?? undefined}
          onClose={() => setEditing(undefined)}
          // Перший створений склад одразу стає поточним — інакше мапа й дашборд лишаться порожніми
          onSaved={(saved) => {
            if (editing === null && warehouses.length === 0) selectWarehouse(saved.warehouse_id);
          }}
        />
      )}
    </>
  );
}
