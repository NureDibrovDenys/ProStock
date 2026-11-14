import { useQuery } from '@tanstack/react-query';
import { CalendarDays, FileText, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getCounterparties } from '../api/directories';
import { ORDER_STATUS_LABELS, getInboundOrders, inboundNumber } from '../api/orders';
import type { OrderStatus } from '../api/types';
import { Button } from '../components/Button';
import { ErrorState, LoadingState, PageHeader } from '../components/ui';
import { cx } from '../lib/cx';
import { formatNumber, plural } from '../lib/format';
import styles from './OrdersPage.module.css';

const OUTBOUND_SOON = 'Вихідні накладні з’являться разом з API вихідних накладних';
const FILTERS_SOON = 'Фільтри з’являться разом зі сторінкою списку накладних';

const dateFormat = new Intl.DateTimeFormat('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' });

/** Поточний місяць для фільтра дат, як у макеті: «01.11 – 30.11.2026». */
function currentMonthLabel(): string {
  const now = new Date();
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  return `01.${mm} – ${String(last.getDate()).padStart(2, '0')}.${mm}.${now.getFullYear()}`;
}

export function StatusPill({ status }: { status: OrderStatus }) {
  return <span className={cx(styles.status, styles[`status-${status}`])}>{ORDER_STATUS_LABELS[status] ?? status}</span>;
}

/**
 * Список накладних. Поки що робоча лише кнопка «+ Прихідна накладна» і перегляд прихідних;
 * фільтри, пошук і вихідні накладні — наступні задачі.
 */
export function OrdersPage() {
  const navigate = useNavigate();
  const ordersQuery = useQuery({ queryKey: ['inbound-orders'], queryFn: () => getInboundOrders({ page_size: 100 }) });
  const suppliersQuery = useQuery({ queryKey: ['directories', 'suppliers'], queryFn: () => getCounterparties('suppliers') });

  const orders = ordersQuery.data ?? [];
  const supplierName = (id: number) =>
    suppliersQuery.data?.find((supplier) => supplier.id === id)?.company_name ?? `Постачальник №${id}`;

  const createButtons = (
    <>
      <Button variant="secondary" disabled title={OUTBOUND_SOON}>
        + Вихідна накладна
      </Button>
      <Button to="/orders/inbound/new">+ Прихідна накладна</Button>
    </>
  );

  return (
    <>
      <PageHeader
        title="Накладні"
        subtitle={ordersQuery.data ? `Усього ${formatNumber(orders.length)}` : undefined}
        actions={createButtons}
      />

      <div className={styles.filters} title={FILTERS_SOON}>
        <div className={styles.pills}>
          <span className={cx(styles.pill, styles.pillActive)}>Усі</span>
          <span className={styles.pill}>Прихідні</span>
          <span className={styles.pill}>Вихідні</span>
        </div>
        <select className={styles.control} disabled aria-label="Статус">
          <option>Статус: усі</option>
        </select>
        <span className={cx(styles.control, styles.dates)} aria-disabled>
          <CalendarDays size={14} aria-hidden />
          {currentMonthLabel()}
        </span>
        <label className={styles.search}>
          <Search size={14} aria-hidden />
          <input type="search" placeholder="Пошук за номером або контрагентом" disabled />
        </label>
      </div>

      {ordersQuery.isPending && <LoadingState />}
      {ordersQuery.isError && <ErrorState error={ordersQuery.error} onRetry={() => ordersQuery.refetch()} />}

      {ordersQuery.data &&
        (orders.length === 0 ? (
          <section className={styles.empty}>
            <span className={styles.emptyIcon} aria-hidden>
              <FileText size={26} />
            </span>
            <h2 className={styles.emptyTitle}>Накладних ще немає</h2>
            <p className={styles.emptyText}>
              Створіть прихідну накладну, щоб прийняти товар на склад, або вихідну — щоб відвантажити його одержувачу.
            </p>
            <div className={styles.emptyActions}>{createButtons}</div>
          </section>
        ) : (
          <ul className={styles.rows}>
            {orders.map((order) => (
              <li key={order.inbound_order_id}>
                <button
                  type="button"
                  className={styles.row}
                  onClick={() => navigate(`/orders/inbound/${order.inbound_order_id}/edit`)}
                >
                  <span className={styles.kind}>Прихідна</span>
                  <span className={styles.main}>
                    <span className={styles.number}>{inboundNumber(order.inbound_order_id)}</span>
                    <span className={styles.meta}>
                      {supplierName(order.supplier_id)} · док. {order.invoice_number}
                    </span>
                  </span>
                  <span className={styles.date}>
                    {dateFormat.format(new Date(order.expected_delivery_date))}
                    <span className={styles.meta}>
                      {order.items.length} {plural(order.items.length, ['позиція', 'позиції', 'позицій'])}
                    </span>
                  </span>
                  <StatusPill status={order.order_status} />
                </button>
              </li>
            ))}
          </ul>
        ))}
    </>
  );
}
