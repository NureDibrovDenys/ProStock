import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Loader } from 'lucide-react';
import { useMemo, useState, type FormEvent } from 'react';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import type { InactiveReason, Shelf, ShelfInput, ShelfPatch } from '../api/types';
import { createShelf, updateShelf } from '../api/warehouse';
import { mapServerErrors } from '../lib/validation';
import { Button } from './Button';
import { Input } from './Input';
import { Modal } from './Modal';
import { Select } from './Select';
import styles from './ShelfFormModal.module.css';

type FormStatus = 'active' | 'inactive';

type FormState = {
  code: string;
  width: string;
  length: string;
  height: string;
  max_weight: string;
  status: FormStatus;
  inactive_reason: InactiveReason | '';
};

type Errors = Partial<Record<keyof FormState, string>>;

const FORM_FIELDS: Array<keyof FormState> = [
  'code',
  'width',
  'length',
  'height',
  'max_weight',
  'status',
  'inactive_reason',
];

/** Причини недоступності полиці (backend: InactiveReason) - спільні для форми та сторінки стелажа. */
export const INACTIVE_REASONS: Array<{ value: InactiveReason; label: string }> = [
  { value: 'damaged', label: 'Пошкодження' },
  { value: 'maintenance', label: 'Технічне обслуговування' },
  { value: 'stocktaking', label: 'Інвентаризація' },
  { value: 'quality_control', label: 'Контроль якості' },
  { value: 'other', label: 'Інше' },
];

function parseDecimal(value: string): number | null {
  const n = Number(value.replace(',', '.').trim());
  return value.trim() && Number.isFinite(n) ? n : null;
}

/** Габарити - decimal(8, 2) > 0 на бекенді: до 6 цифр до коми, 2 після. */
function validateDimension(raw: string): string | undefined {
  const trimmed = raw.trim();
  if (parseDecimal(trimmed) === null) return 'Вкажіть число';
  if (parseDecimal(trimmed)! <= 0) return 'Значення має бути більшим за 0';
  if (!/^\d{1,6}([.,]\d{1,2})?$/.test(trimmed)) return 'До 6 цифр і не більше 2 знаків після коми';
  return undefined;
}

/** Навантаження - decimal(10, 3) > 0 на бекенді: до 7 цифр до коми, 3 після. */
function validateWeight(raw: string): string | undefined {
  const trimmed = raw.trim();
  if (parseDecimal(trimmed) === null) return 'Вкажіть число';
  if (parseDecimal(trimmed)! <= 0) return 'Значення має бути більшим за 0';
  if (!/^\d{1,7}([.,]\d{1,3})?$/.test(trimmed)) return 'До 7 цифр і не більше 3 знаків після коми';
  return undefined;
}

/** Обмеження як у ShelfCreate на бекенді. */
function validate(form: FormState, isEdit: boolean): Errors {
  const errors: Errors = {};
  if (!isEdit) {
    if (!form.code.trim()) errors.code = 'Вкажіть код полиці';
    else if (form.code.trim().length > 50) errors.code = 'Максимум 50 символів';
  }
  for (const field of ['width', 'length', 'height'] as const) {
    const error = validateDimension(form[field]);
    if (error) errors[field] = error;
  }
  const weightError = validateWeight(form.max_weight);
  if (weightError) errors.max_weight = weightError;
  // Статус «occupied» не можна встановити вручну - його визначають складські операції
  if (form.status === 'inactive' && !form.inactive_reason) {
    errors.inactive_reason = 'Вкажіть причину недоступності';
  }
  return errors;
}

/**
 * Створення (shelf не передано) або редагування полиці стелажа.
 * Код полиці змінювати не можна - у PATCH його просто немає, тому в редагуванні поле лише для читання.
 */
export function ShelfFormModal({
  warehouseId,
  rackCode,
  shelf,
  onClose,
}: {
  warehouseId: number;
  rackCode: string;
  shelf?: Shelf;
  onClose: () => void;
}) {
  const isEdit = shelf !== undefined;
  const [form, setForm] = useState<FormState>({
    code: shelf?.shelf_code ?? '',
    width: shelf?.width ?? '',
    length: shelf?.length ?? '',
    height: shelf?.height ?? '',
    max_weight: shelf?.max_weight ?? '',
    status: shelf?.status === 'inactive' ? 'inactive' : 'active',
    inactive_reason: shelf?.inactive_reason ?? '',
  });
  const [errors, setErrors] = useState<Errors>({});
  const queryClient = useQueryClient();

  const mutation = useMutation({
    // Редагування надсилає лише змінені поля (PATCH), створення - усі
    mutationFn: (data: ShelfInput | ShelfPatch) =>
      isEdit
        ? updateShelf(warehouseId, rackCode, shelf.shelf_id, data as ShelfPatch)
        : createShelf(warehouseId, rackCode, data as ShelfInput),
    onSuccess: (saved) => {
      // Полиці стелажа (ця сторінка), список стелажів і дашборд залежать від кількості/стану полиць
      void queryClient.invalidateQueries({ queryKey: ['shelves', warehouseId, rackCode] });
      void queryClient.invalidateQueries({ queryKey: ['racks', warehouseId] });
      void queryClient.invalidateQueries({ queryKey: ['dashboard', warehouseId] });
      toast.success(
        isEdit
          ? `Полицю «${saved.shelf_code}» оновлено`
          : `Полицю «${saved.shelf_code}» створено в стелажі «${rackCode}»`,
      );
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.details.length > 0) {
        setErrors((prev) => ({ ...prev, ...mapServerErrors(error.details, FORM_FIELDS) }));
      }
    },
  });

  const serverError = useMemo(() => {
    const error = mutation.error;
    if (!error) return null;
    if (
      error instanceof ApiError &&
      error.status === 422 &&
      error.details.some((d) => d.field && FORM_FIELDS.includes(d.field as keyof FormState))
    ) {
      return 'Перевірте виділені поля';
    }
    if (error instanceof ApiError && error.status === 403) {
      return 'Керувати полицями може лише адміністратор або менеджер складу';
    }
    return error instanceof Error ? error.message : 'Не вдалося зберегти полицю';
  }, [mutation.error]);

  const update = (field: keyof FormState) => (value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
    mutation.reset();
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    // Модалка рендериться порталом, але React-подія все одно спливає до батьківської форми
    event.stopPropagation();
    if (mutation.isPending) return;
    const nextErrors = validate(form, isEdit);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    const width = parseDecimal(form.width)!;
    const length = parseDecimal(form.length)!;
    const height = parseDecimal(form.height)!;
    const maxWeight = parseDecimal(form.max_weight)!;
    // validate() вище гарантує: при inactive причина обрана, при active - порожня
    const reason: InactiveReason | null =
      form.status === 'inactive' && form.inactive_reason !== '' ? form.inactive_reason : null;

    if (!isEdit) {
      mutation.mutate({
        code: form.code.trim(),
        width,
        length,
        height,
        max_weight: maxWeight,
        status: form.status,
        inactive_reason: reason,
      });
      return;
    }

    // PATCH - лише змінені поля.
    // Якщо статус inactive → active, причина потрапляє в changes як null - це критично:
    // без неї бекенд побачить стару причину при активному статусі й відхилить запит (422).
    const changes: ShelfPatch = {};
    if (width !== Number(shelf.width)) changes.width = width;
    if (length !== Number(shelf.length)) changes.length = length;
    if (height !== Number(shelf.height)) changes.height = height;
    if (maxWeight !== Number(shelf.max_weight)) changes.max_weight = maxWeight;
    if (form.status !== shelf.status) changes.status = form.status;
    if (reason !== shelf.inactive_reason) changes.inactive_reason = reason;
    if (Object.keys(changes).length === 0) {
      toast.info('Змін немає - нічого зберігати');
      return;
    }
    mutation.mutate(changes);
  };

  return (
    <Modal
      title={isEdit ? 'Редагування полиці' : 'Нова полиця'}
      subtitle={
        isEdit
          ? `Стелаж «${rackCode}» · QR: ${shelf.qr}`
          : `Стелаж «${rackCode}» - полиця з’явиться у списку після створення`
      }
      onClose={onClose}
      size="sm"
      dismissible={!mutation.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Скасувати
          </Button>
          <Button type="submit" form="shelf-form" variant="save" disabled={mutation.isPending}>
            {mutation.isPending ? (
              <>
                <Loader size={17} className="spin" aria-hidden /> Збереження…
              </>
            ) : (
              <>
                <Check size={17} aria-hidden /> {isEdit ? 'Зберегти' : 'Створити'}
              </>
            )}
          </Button>
        </>
      }
    >
      <form id="shelf-form" className={styles.form} onSubmit={handleSubmit} noValidate>
        <Input
          label="Код полиці *"
          placeholder="A-01"
          value={form.code}
          onChange={(e) => update('code')(e.target.value)}
          error={errors.code}
          maxLength={50}
          disabled={isEdit}
          hint={isEdit ? 'Код полиці змінити не можна' : `QR згенерується автоматично: R${rackCode}-${form.code.trim() || '…'}`}
          autoFocus={!isEdit}
        />
        <div className={styles.row}>
          <Input
            label="Ширина, м *"
            inputMode="decimal"
            placeholder="1.2"
            value={form.width}
            onChange={(e) => update('width')(e.target.value)}
            error={errors.width}
          />
          <Input
            label="Довжина, м *"
            inputMode="decimal"
            placeholder="2.4"
            value={form.length}
            onChange={(e) => update('length')(e.target.value)}
            error={errors.length}
          />
        </div>
        <div className={styles.row}>
          <Input
            label="Висота, м *"
            inputMode="decimal"
            placeholder="1.5"
            value={form.height}
            onChange={(e) => update('height')(e.target.value)}
            error={errors.height}
          />
          <Input
            label="Макс. навантаження, кг *"
            inputMode="decimal"
            placeholder="500"
            value={form.max_weight}
            onChange={(e) => update('max_weight')(e.target.value)}
            error={errors.max_weight}
          />
        </div>
        <Select
          label="Статус *"
          value={form.status}
          onChange={(e) => update('status')(e.target.value)}
        >
          <option value="active">Активна</option>
          <option value="inactive">Не функціонує</option>
        </Select>
        {form.status === 'inactive' && (
          <Select
            label="Причина недоступності *"
            value={form.inactive_reason}
            onChange={(e) => update('inactive_reason')(e.target.value)}
            error={errors.inactive_reason}
          >
            <option value="">Оберіть причину…</option>
            {INACTIVE_REASONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        )}
        {serverError && (
          <p className={styles.serverError} role="alert">
            {serverError}
          </p>
        )}
      </form>
    </Modal>
  );
}
