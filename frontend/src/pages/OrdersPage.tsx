import { useQuery } from '@tanstack/react-query';
import { CalendarDays, FileText, Search } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ORDER_STATUS_LABELS, ORDER_TYPE_LABELS, getOrders } from '../api/orders';
import type { OrderStatus, OrderType } from '../api/types';
import { Button } from '../components/Button';
import { ErrorState, LoadingState, PageHeader } from '../components/ui';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { cx } from '../lib/cx';
import { formatNumber, plural } from '../lib/format';
import styles from './OrdersPage.module.css';

const dateFormat = new Intl.DateTimeFormat('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' });

const TYPE_FILTERS: Array<{ value: 'all' | OrderType; label: string }> = [
  { value: 'all', label: 'Усі' },
  { value: 'inbound', label: 'Прихідні' },
  { value: 'outbound', label: 'Вихідні' },
];

const STATUS_OPTIONS: Array<{ value: 'all' | OrderStatus; label: string }> = [
  { value: 'all', label: 'Статус: усі' },
  { value: 'draft', label: 'Статус: чернетка' },
  { value: 'in_progress', label: 'Статус: в обробці' },
  { value: 'ready', label: 'Статус: сформовано завдання' },
  { value: 'completed', label: 'Статус: завершено' },
  { value: 'canceled', label: 'Статус: скасовано' },
];

export function StatusPill({ status }: { status: OrderStatus }) {
  return <span className={cx(styles.status, styles[`status-${status}`])}>{ORDER_STATUS_LABELS[status] ?? status}</span>;
}

export function OrdersPage() {
  const navigate = useNavigate();
  const [type, setType] = useState<'all' | OrderType>('all');
  const [status, setStatus] = useState<'all' | OrderStatus>('all');
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);

  const ordersQuery = useQuery({
    queryKey: ['orders', type, status, debouncedSearch, dateFrom, dateTo],
    queryFn: () =>
      getOrders({
        order_type: type === 'all' ? undefined : type,
        order_status: status === 'all' ? undefined : status,
        search: debouncedSearch.trim() || undefined,
        date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
        page_size: 100,
      }),
  });

  const orders = ordersQuery.data?.items ?? [];
  const total = ordersQuery.data?.total ?? 0;

  const createButtons = (
    <>
      <Button variant="secondary" to="/orders/outbound/new">
        + Вихідна накладна
      </Button>
      <Button to="/orders/inbound/new">+ Прихідна накладна</Button>
    </>
  );

  const editPath = (orderType: OrderType, orderId: number) =>
    orderType === 'inbound' ? `/orders/inbound/${orderId}/edit` : `/orders/outbound/${orderId}/edit`;

  return (
    <>
      <PageHeader
        title="Накладні"
        subtitle={ordersQuery.data ? `Усього ${formatNumber(total)}` : undefined}
        actions={createButtons}
      />

      <div className={styles.filters}>
        <div className={styles.pills} role="group" aria-label="Тип накладної">
          {TYPE_FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              className={cx(styles.pill, type === option.value && styles.pillActive)}
              aria-pressed={type === option.value}
              onClick={() => setType(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <select
          className={styles.control}
          value={status}
          aria-label="Статус"
          onChange={(event) => setStatus(event.target.value as 'all' | OrderStatus)}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <label className={cx(styles.control, styles.dateInput)}>
          <CalendarDays size={14} aria-hidden />
          <input
            type="date"
            value={dateFrom}
            aria-label="Дата з"
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </label>
        <label className={cx(styles.control, styles.dateInput)}>
          <CalendarDays size={14} aria-hidden />
          <input
            type="date"
            value={dateTo}
            aria-label="Дата по"
            onChange={(event) => setDateTo(event.target.value)}
          />
        </label>

        <label className={styles.search}>
          <Search size={14} aria-hidden />
          <input
            type="search"
            value={search}
            placeholder="Пошук за номером або контрагентом"
            aria-label="Пошук за номером або контрагентом"
            onChange={(event) => setSearch(event.target.value)}
          />
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
            <h2 className={styles.emptyTitle}>Накладних не знайдено</h2>
            <p className={styles.emptyText}>
              Змініть фільтри або створіть накладну: прихідну - щоб прийняти товар на склад, вихідну - щоб
              відвантажити його одержувачу.
            </p>
            <div className={styles.emptyActions}>{createButtons}</div>
          </section>
        ) : (
          <ul className={styles.rows}>
            {orders.map((order) => (
              <li key={`${order.order_type}-${order.order_id}`}>
                <button
                  type="button"
                  className={styles.row}
                  onClick={() => navigate(editPath(order.order_type, order.order_id))}
                >
                  <span className={styles.kind}>{ORDER_TYPE_LABELS[order.order_type]}</span>
                  <span className={styles.main}>
                    <span className={styles.number}>{order.number}</span>
                    <span className={styles.meta}>
                      {order.counterparty_name} · док. {order.invoice_number}
                    </span>
                  </span>
                  <span className={styles.date}>
                    {dateFormat.format(new Date(order.date))}
                    <span className={styles.meta}>
                      {order.items_count} {plural(order.items_count, ['позиція', 'позиції', 'позицій'])} ·{' '}
                      {formatNumber(Number(order.total_quantity))} од.
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
