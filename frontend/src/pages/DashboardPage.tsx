import { useQuery } from '@tanstack/react-query';
import { getDashboard } from '../api/warehouse';
import { useCurrentWarehouse } from '../hooks/useCurrentWarehouse';
import { useWarehouseName } from '../hooks/useWarehouse';
import { RackFillChart } from '../components/RackFillChart';
import { StatCard, StatGrid } from '../components/StatCard';
import { Card, ErrorState, LoadingState, PageHeader } from '../components/ui';
import { formatNumber, formatOperationTime, formatSigned, formatTime, plural } from '../lib/format';
import styles from './DashboardPage.module.css';

export function DashboardPage() {
  const warehouseId = useCurrentWarehouse();
  const warehouseName = useWarehouseName();
  const query = useQuery({
    queryKey: ['dashboard', warehouseId],
    queryFn: () => getDashboard(warehouseId),
  });
  const data = query.data;

  return (
    <>
      <PageHeader
        title="Головна"
        subtitle={
          data
            ? `Склад ${warehouseName} · статистика станом на сьогодні, ${formatTime(data.updated_at)}`
            : `Склад ${warehouseName}`
        }
      />

      {query.isPending && <LoadingState />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {data && (
        <>
          <StatGrid>
            <StatCard
              label="Стелажів"
              value={String(data.racks_count)}
              caption={`на ${data.zones_count} ${plural(data.zones_count, ['зоні', 'зонах', 'зонах'])} складу`}
            />
            <StatCard
              label="Заповненість"
              value={`${data.fill_percent}%`}
              caption={`${formatSigned(data.fill_change_week)}% за тиждень`}
            />
            <StatCard
              label="На зміні"
              value={`${data.on_shift} / ${data.employees_total}`}
              caption={plural(data.employees_total, ['співробітник', 'співробітники', 'співробітників'])}
            />
            <StatCard
              label="Вільна площа"
              value={`${formatNumber(data.free_area_m2)} м²`}
              caption={`з ${formatNumber(data.total_area_m2)} м²`}
            />
          </StatGrid>

          <div className={styles.row}>
            <Card title="Заповненість стелажів, %" className={styles.chart}>
              <RackFillChart data={data.rack_fill} />
            </Card>

            <Card title="Останні операції" className={styles.operations}>
              {data.recent_operations.length === 0 ? (
                <p className={styles.muted}>Операцій ще немає</p>
              ) : (
                <ul className={styles.operationList}>
                  {data.recent_operations.map((op) => (
                    <li key={op.log_id}>
                      {formatOperationTime(op.timestamp)} · {op.action}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  );
}
