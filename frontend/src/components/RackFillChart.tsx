import { Link } from 'react-router-dom';
import type { DashboardStats } from '../api/types';
import { cx } from '../lib/cx';
import { CRITICAL_FILL } from './ui';
import styles from './RackFillChart.module.css';

/** Стовпчикова діаграма заповненості стелажів. Висота стовпця 100% = 280px, як у макеті. */
export function RackFillChart({ data }: { data: DashboardStats['rack_fill'] }) {
  if (data.length === 0) {
    return <p className={styles.empty}>Стелажі ще не додані</p>;
  }

  return (
    <div className={styles.scroll}>
      <div className={styles.plot}>
        {data.map((rack) => {
          const percent = Math.min(100, Math.max(0, rack.fill_percent));
          const critical = percent >= CRITICAL_FILL;
          return (
            <Link
              key={rack.rack_code}
              to={`/warehouse/racks/${encodeURIComponent(rack.rack_code)}`}
              className={styles.column}
              aria-label={`Стелаж ${rack.rack_code}: ${percent}%${critical ? ', критично' : ''}`}
            >
              <span className={styles.bars}>
                <span className={styles.value}>{percent}%</span>
                <span
                  className={cx(styles.bar, critical && styles.critical)}
                  style={{ height: `${percent}%` }}
                />
              </span>
              <span className={styles.label}>{rack.rack_code}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
