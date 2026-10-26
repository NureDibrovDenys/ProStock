import { useId, type ComponentPropsWithRef } from 'react';
import { cx } from '../lib/cx';
import styles from './Input.module.css';

type InputProps = ComponentPropsWithRef<'input'> & {
  label: string;
  error?: string;
  /** Підказка під полем (показується, якщо немає помилки). */
  hint?: string;
};

export function Input({ label, error, hint, className, id, ...rest }: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <input
        id={inputId}
        className={cx(styles.box, error && styles.invalid)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        aria-label={rest['aria-label'] ?? label}
        {...rest}
      />
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : (
        hint && <p className={styles.hint}>{hint}</p>
      )}
    </div>
  );
}
