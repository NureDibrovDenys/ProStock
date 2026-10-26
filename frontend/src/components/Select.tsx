import { useId, type ComponentPropsWithRef, type ReactNode } from 'react';
import { cx } from '../lib/cx';
import styles from './Input.module.css';
import selectStyles from './Select.module.css';

type SelectProps = ComponentPropsWithRef<'select'> & {
  label: string;
  error?: string;
  children: ReactNode;
};

export function Select({ label, error, className, id, children, ...rest }: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const errorId = `${selectId}-error`;

  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={selectId} className={styles.label}>
        {label}
      </label>
      <select
        id={selectId}
        className={cx(styles.box, selectStyles.box, error && styles.invalid)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        aria-label={rest['aria-label'] ?? label}
        {...rest}
      >
        {children}
      </select>
      {error && (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
