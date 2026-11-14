// Спільне для форм прихідної та вихідної накладних: поля, дати, кількість.
import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from '../lib/cx';
import styles from './OrderForm.module.css';

export const QUANTITY_PATTERN = /^\d{1,8}([.,]\d{1,2})?$/;

export const parseQuantity = (value: string) => Number(value.trim().replace(',', '.'));

/** Кількість з API ("120.00") → значення поля ("120"). */
export const quantityToInput = (value: string) => String(Number(value)).replace('.', ',');

/** Кількість рядка, якщо вона коректна й додатна, інакше null. */
export function validQuantity(value: string): number | null {
  if (!QUANTITY_PATTERN.test(value.trim())) return null;
  const quantity = parseQuantity(value);
  return quantity > 0 ? quantity : null;
}

// ── Дати: бекенд зберігає timestamptz, у формі — локальна дата yyyy-mm-dd ──

const pad = (n: number) => String(n).padStart(2, '0');
export const toDateInput = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
export const fromDateInput = (value: string) => new Date(`${value}T00:00:00`).toISOString();

export function Field({
  label,
  htmlFor,
  error,
  hint,
  wide,
  children,
}: {
  label: string;
  htmlFor?: string;
  error?: string;
  hint?: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={cx(styles.field, wide && styles.wide)}>
      {htmlFor ? (
        <label htmlFor={htmlFor} className={styles.label}>
          {label}
        </label>
      ) : (
        <span className={styles.label}>{label}</span>
      )}
      {children}
      {error ? (
        <span className={styles.fieldError} role="alert">
          <AlertTriangle size={13} aria-hidden /> {error}
        </span>
      ) : (
        hint && <span className={styles.hint}>{hint}</span>
      )}
    </div>
  );
}
