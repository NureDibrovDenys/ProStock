import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import type { ShelfStatus } from '../api/types';
import { getRackDetails } from '../api/warehouse';
import { Button } from '../components/Button';
import { StatCard, StatGrid } from '../components/StatCard';
import { ErrorState, LoadingState, PageHeader, ProgressBar } from '../components/ui';
import { useCurrentWarehouse } from '../hooks/useCurrentWarehouse';
import { formatRelativeDay, plural } from '../lib/format';
import styles from './RackPage.module.css';

const SHELF_STATUS_LABELS: Record<ShelfStatus, string> = {
  active: '',
  occupied: '',
  inactive: ' · не функціонує',
};

export function RackPage() {
  const warehouseId = useCurrentWarehouse();
  const { rackCode = '' } = useParams();

  const query = useQuery({
    queryKey: ['rack', warehouseId, rackCode],
    queryFn: () => getRackDetails(warehouseId, rackCode),
  });
  const rack = query.data;

  const capacity = rack?.shelves.reduce((sum, s) => sum + s.capacity, 0) ?? 0;
  const occupied = rack?.shelves.reduce((sum, s) => sum + s.occupied, 0) ?? 0;
  const free = capacity - occupied;
  const fill = capacity ? Math.round((occupied / capacity) * 100) : 0;

  return (
    <>
      <div className={styles.back}>
        <Button variant="secondary" to="/warehouse">
          ← Назад до складу
        </Button>
      </div>

      <PageHeader
        title={`Стелаж ${rackCode}`}
        subtitle={
          rack
            ? [
                rack.zone_name,
                `${rack.shelves.length} ${plural(rack.shelves.length, ['полиця', 'полиці', 'полиць'])}`,
                `оновлено ${formatRelativeDay(rack.updated_at)}`,
              ]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
      />

      {query.isPending && <LoadingState />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {rack && (
        <>
          <StatGrid>
            <StatCard label="Заповненість" value={`${fill}%`} caption="від загальної місткості" />
            <StatCard label="Місткість" value={String(capacity)} caption={plural(capacity, ['палетомісце', 'палетомісця', 'палетомісць'])} />
            <StatCard label="Зайнято" value={String(occupied)} caption={plural(occupied, ['палета', 'палети', 'палет'])} />
            <StatCard label="Вільно" value={String(free)} caption={plural(free, ['палетомісце', 'палетомісця', 'палетомісць'])} />
          </StatGrid>

          <section className={styles.shelves}>
            <h2 className={styles.title}>Полиці</h2>
            {rack.shelves.length === 0 ? (
              <p className={styles.empty}>У стелажа ще немає полиць</p>
            ) : (
              <div className={styles.scroll}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Полиця</th>
                      <th>Товар</th>
                      <th>Зайнято</th>
                      <th>Заповненість</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rack.shelves.map((shelf) => {
                      const percent = shelf.capacity ? Math.round((shelf.occupied / shelf.capacity) * 100) : 0;
                      return (
                        <tr key={shelf.shelf_id}>
                          <td className={styles.shelfName}>
                            {shelf.shelf_code}
                            {SHELF_STATUS_LABELS[shelf.shelf_status]}
                          </td>
                          <td>{shelf.product_name ?? '—'}</td>
                          <td>
                            {shelf.occupied} / {shelf.capacity} палет
                          </td>
                          <td>
                            <div className={styles.fill}>
                              <ProgressBar percent={percent} />
                              <span className={styles.percent}>{percent}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
