import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useId, useState, type KeyboardEvent } from 'react';
import { getProducts } from '../api/products';
import type { Product } from '../api/types';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { cx } from '../lib/cx';
import styles from './ProductPicker.module.css';

export const productLabel = (product: Product) => `${product.sku_code} · ${product.name}`;

type Props = {
  value: Product | null;
  onChange: (product: Product | null) => void;
  invalid?: boolean;
  disabled?: boolean;
  /** Товари, які не можна обрати (вже є в інших рядках) — показуються неактивними з поясненням. */
  isTaken?: (product: Product) => boolean;
  takenLabel?: string;
  'aria-label'?: string;
};

export function ProductPicker({
  value,
  onChange,
  invalid,
  disabled,
  isTaken,
  takenLabel = 'уже додано',
  'aria-label': ariaLabel,
}: Props) {
  const listId = useId();
  const [text, setText] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const shown = text ?? (value ? productLabel(value) : '');
  const search = useDebouncedValue(text?.trim() ?? '', 250);

  const query = useQuery({
    queryKey: ['products', 'picker', search],
    queryFn: () => getProducts({ search: search || undefined, page_size: 8, sort_by: 'sku_code' }),
    enabled: open,
    staleTime: 30_000,
  });
  const options = query.data?.items ?? [];

  const choose = (product: Product) => {
    if (isTaken?.(product)) return;
    onChange(product);
    setText(null);
    setOpen(false);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      if (options.length > 0) {
        const step = event.key === 'ArrowDown' ? 1 : -1;
        setActive((prev) => (prev + step + options.length) % options.length);
      }
    } else if (event.key === 'Enter' && open) {
      event.preventDefault();
      if (options[active]) choose(options[active]);
    } else if (event.key === 'Escape') {
      setOpen(false);
      setText(null);
    }
  };

  return (
    <div className={styles.picker}>
      <Search size={14} className={styles.icon} aria-hidden />
      <input
        className={cx(styles.input, invalid && styles.invalid)}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        aria-label={ariaLabel ?? 'Товар'}
        placeholder="SKU або назва"
        autoComplete="off"
        disabled={disabled}
        value={shown}
        title={value ? productLabel(value) : undefined}
        onChange={(event) => {
          setText(event.target.value);
          setActive(0);
          setOpen(true);
          if (value) onChange(null);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          setOpen(false);
          setText(null);
        }}
        onKeyDown={handleKeyDown}
      />
      {open && (
        <ul id={listId} role="listbox" className={styles.list}>
          {query.isPending && <li className={styles.note}>Пошук…</li>}
          {query.isError && <li className={styles.note}>Не вдалося завантажити товари</li>}
          {query.data && options.length === 0 && <li className={styles.note}>Нічого не знайдено</li>}
          {options.map((product, index) => {
            const taken = isTaken?.(product) ?? false;
            return (
              <li
                key={product.product_id}
                role="option"
                aria-selected={index === active}
                aria-disabled={taken || undefined}
                className={cx(styles.option, index === active && styles.optionActive, taken && styles.optionTaken)}
                // mousedown, щоб вибір спрацював раніше за blur поля
                onMouseDown={(event) => {
                  event.preventDefault();
                  choose(product);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <span className={styles.sku}>{product.sku_code}</span>
                {product.name}
                {taken && <span className={styles.takenNote}>{takenLabel}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
