import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cx } from '../../lib/cx';
import type { LabelData } from './labelData';
import styles from './LabelPrinter.module.css';
import { QrLabel } from './QrLabel';

/**
 * roll - по одній етикетці 58×40 мм на сторінку (термопринтер);
 * sheet - сітка на аркуші A4: 3 колонки × 7 рядів = 21 етикетка, з лініями для різання.
 */
export type LabelLayout = 'roll' | 'sheet';

/** Скільки етикеток 58×40 мм вміщується на A4 з полями з LabelPrinter.module.css. */
const LABELS_PER_SHEET = 3 * 7;

type LabelPrinterProps = {
  labels: LabelData[];
  layout?: LabelLayout;
  /** Викликається після закриття діалогу друку: батько прибирає компонент. */
  onDone: () => void;
};

function chunk<T>(items: T[], size: number): T[][] {
  const result: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    result.push(items.slice(i, i + size));
  }
  return result;
}

/**
 * Друкує етикетки. Монтується на час друку: рендерить аркуші в body, відкриває
 * системний діалог друку і чекає `afterprint`. На екрані аркуші приховані,
 * а під час друку ховається решта сторінки.
 */
export function LabelPrinter({ labels, layout = 'roll', onDone }: LabelPrinterProps) {
  const started = useRef(false);
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  useEffect(() => {
    // StrictMode у dev запускає ефект двічі, а діалог друку потрібен один.
    if (started.current) return;
    started.current = true;

    window.addEventListener('afterprint', () => onDoneRef.current(), { once: true });
    window.print();
  }, []);

  // Сторінки розбиваємо самі, а не покладаємося на те, як браузер розірве сітку між аркушами.
  const pages = layout === 'sheet' ? chunk(labels, LABELS_PER_SHEET) : labels.map((label) => [label]);

  return createPortal(
    <div className={cx(styles.root, 'print-sheet')} aria-hidden>
      {pages.map((page) => (
        <div key={page[0].qr} className={layout === 'sheet' ? styles.sheetPage : styles.rollPage}>
          {page.map((label) => (
            <QrLabel key={label.qr} label={label} className={layout === 'sheet' ? styles.cutLabel : undefined} />
          ))}
        </div>
      ))}
    </div>,
    document.body,
  );
}
