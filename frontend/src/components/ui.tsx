// Дрібні спільні компоненти інтерфейсу
import type { ReactNode } from 'react';
import { cx } from '../lib/cx';
import styles from './ui.module.css';

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className={styles.pageHeader}>
      <div className={styles.pageHeaderText}>
        <h1 className={styles.pageTitle}>{title}</h1>
        {subtitle && <p className={styles.pageSubtitle}>{subtitle}</p>}
      </div>
      {actions && <div className={styles.pageActions}>{actions}</div>}
    </div>
  );
}

export function Card({ title, className, children }: { title?: string; className?: string; children: ReactNode }) {
  return (
    <section className={cx(styles.card, className)}>
      {title && <h2 className={styles.cardTitle}>{title}</h2>}
      {children}
    </section>
  );
}

export function Avatar({ firstName, lastName, size = 'md' }: { firstName: string; lastName: string; size?: 'sm' | 'md' }) {
  const initials = `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  return (
    <span className={cx(styles.avatar, styles[`avatar-${size}`])} aria-hidden>
      {initials}
    </span>
  );
}

export function StatusBadge({ onShift }: { onShift: boolean }) {
  return (
    <span className={cx(styles.badge, onShift ? styles.badgeOn : styles.badgeOff)}>
      {onShift ? 'На зміні' : 'Не на зміні'}
    </span>
  );
}

/** Поріг, з якого заповненість вважається критичною й підсвічується червоним. */
export const CRITICAL_FILL = 90;

export function ProgressBar({ percent }: { percent: number }) {
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <div
      className={styles.progress}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cx(styles.progressFill, clamped >= CRITICAL_FILL && styles.progressCritical)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export function LoadingState({ label = 'Завантаження…' }: { label?: string }) {
  return (
    <div className={styles.state} role="status">
      <span className={styles.spinner} aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Не вдалося завантажити дані';
  return (
    <div className={cx(styles.state, styles.stateError)} role="alert">
      {message}
      {onRetry && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Спробувати ще раз
        </button>
      )}
    </div>
  );
}
