import { useQuery } from '@tanstack/react-query';
import { Loader, Printer } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { useState } from 'react';
import { ApiError } from '../api/client';
import { getInboundLpnContainers } from '../api/orders';
import { formatNumber } from '../lib/format';
import { Button } from './Button';
import { LabelPrinter } from './labels/LabelPrinter';
import { lpnLabel } from './labels/labelData';
import styles from './LpnLabelsCard.module.css';

type LpnLabelsCardProps = {
  orderId: number;
  /** Номер накладної для етикетки, наприклад «ПН-000039». */
  orderNumber: string;
};

/**
 * Блок «LPN-коди» на сторінці проведеної прихідної накладної: QR кожної коробки
 * і друк етикеток сіткою на A4. Поки LPN немає, блок не показується зовсім.
 */
export function LpnLabelsCard({ orderId, orderNumber }: LpnLabelsCardProps) {
  const [printing, setPrinting] = useState(false);

  const query = useQuery({
    queryKey: ['inbound-orders', orderId, 'lpn-containers'],
    queryFn: () => getInboundLpnContainers(orderId),
  });

  // 404 - бекенд ще без ендпоінта LPN (або накладну проведено до його появи): блок просто ховаємо.
  if (query.isError && query.error instanceof ApiError && query.error.status === 404) return null;
  if (query.isSuccess && query.data.length === 0) return null;

  return (
    <section className={styles.card}>
      <h2 className={styles.title}>LPN-коди</h2>
      <p className={styles.caption}>Етикетки для коробок, прийнятих на склад.</p>

      {query.isPending && (
        <p className={styles.muted}>
          <Loader size={14} className="spin" aria-hidden /> Завантаження…
        </p>
      )}

      {query.isError && (
        <p className={styles.muted}>
          Не вдалося завантажити LPN-коди.{' '}
          <button type="button" className={styles.retry} onClick={() => query.refetch()}>
            Повторити
          </button>
        </p>
      )}

      {query.isSuccess && (
        <>
          <ul className={styles.grid}>
            {query.data.map((lpn) => (
              <li
                key={lpn.lpn_container_id}
                className={styles.tile}
                title={`${lpn.product_name} · ${formatNumber(Number(lpn.quantity))}${lpn.shelf_code ? ` · полиця ${lpn.shelf_code}` : ''}`}
              >
                <QRCodeSVG value={lpn.code} level="M" marginSize={0} className={styles.qr} />
                <span className={styles.code}>{lpn.code}</span>
              </li>
            ))}
          </ul>

          <Button variant="secondary" block onClick={() => setPrinting(true)} disabled={printing}>
            <Printer size={16} aria-hidden /> Друкувати етикетки
          </Button>

          {printing && (
            <LabelPrinter
              labels={query.data.map((lpn) => lpnLabel(lpn, orderNumber))}
              layout="sheet"
              onDone={() => setPrinting(false)}
            />
          )}
        </>
      )}
    </section>
  );
}
