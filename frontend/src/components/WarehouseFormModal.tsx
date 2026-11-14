import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Loader } from 'lucide-react';
import { useMemo, useState, type FormEvent } from 'react';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import type { Warehouse, WarehouseInput } from '../api/types';
import { createWarehouse, updateWarehouse } from '../api/warehouse';
import { mapServerErrors } from '../lib/validation';
import { Button } from './Button';
import { Input } from './Input';
import { Modal } from './Modal';
import styles from './WarehouseFormModal.module.css';

type FormState = { name: string; address: string; total_area: string };
type Errors = Partial<Record<keyof FormState, string>>;

const FORM_FIELDS: Array<keyof FormState> = ['name', 'address', 'total_area'];

function parseArea(value: string): number | null {
  const n = Number(value.replace(',', '.').trim());
  return value.trim() && Number.isFinite(n) ? n : null;
}

/** Обмеження як у WarehouseCreate на бекенді. */
function validate(form: FormState): Errors {
  const errors: Errors = {};
  if (!form.name.trim()) errors.name = 'Вкажіть назву складу';
  else if (form.name.trim().length > 150) errors.name = 'Максимум 150 символів';
  if (form.address.trim().length > 500) errors.address = 'Максимум 500 символів';
  const area = parseArea(form.total_area);
  if (area === null) errors.total_area = 'Вкажіть площу числом';
  else if (area <= 0) errors.total_area = 'Площа має бути більшою за 0';
  else if (!/^\d+([.,]\d{1,2})?$/.test(form.total_area.trim())) errors.total_area = 'Не більше 2 знаків після коми';
  return errors;
}

/**
 * Створення (warehouse не передано) або редагування складу.
 * onSaved отримує збережений склад — напр., щоб одразу зробити новий склад поточним.
 */
export function WarehouseFormModal({
  warehouse,
  onClose,
  onSaved,
}: {
  warehouse?: Warehouse;
  onClose: () => void;
  onSaved?: (warehouse: Warehouse) => void;
}) {
  const queryClient = useQueryClient();
  const isEdit = warehouse !== undefined;
  const [form, setForm] = useState<FormState>({
    name: warehouse?.warehouse_name ?? '',
    address: warehouse?.warehouse_address ?? '',
    total_area: warehouse ? String(warehouse.total_warehouse_area) : '',
  });
  const [errors, setErrors] = useState<Errors>({});

  const mutation = useMutation({
    // Редагування надсилає лише змінені поля (PATCH), створення — усі
    mutationFn: (data: Partial<WarehouseInput>) =>
      isEdit ? updateWarehouse(warehouse.warehouse_id, data) : createWarehouse(data as WarehouseInput),
    onSuccess: (saved) => {
      // Список складів використовують перемикач, фільтр співробітників і вибір складу для менеджера
      void queryClient.invalidateQueries({ queryKey: ['warehouses'] });
      void queryClient.invalidateQueries({ queryKey: ['warehouse', saved.warehouse_id] });
      toast.success(isEdit ? `Склад «${saved.warehouse_name}» оновлено` : `Склад «${saved.warehouse_name}» створено`);
      onSaved?.(saved);
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
    if (error instanceof ApiError && error.status === 403) return 'Керувати складами може лише адміністратор';
    return error instanceof Error ? error.message : 'Не вдалося зберегти склад';
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
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    const data: WarehouseInput = {
      name: form.name.trim(),
      address: form.address.trim() || null,
      total_area: parseArea(form.total_area)!,
    };
    if (!isEdit) return mutation.mutate(data);

    // PATCH — лише змінені поля
    const changes: Partial<WarehouseInput> = {};
    if (data.name !== warehouse.warehouse_name) changes.name = data.name;
    if (data.address !== (warehouse.warehouse_address ?? null)) changes.address = data.address;
    if (data.total_area !== Number(warehouse.total_warehouse_area)) changes.total_area = data.total_area;
    if (Object.keys(changes).length === 0) {
      toast.info('Змін немає — нічого зберігати');
      return;
    }
    mutation.mutate(changes);
  };

  return (
    <Modal
      title={isEdit ? 'Редагування складу' : 'Новий склад'}
      subtitle={
        isEdit
          ? warehouse.warehouse_name
          : 'Після створення склад з’явиться в перемикачі та у виборі складу для менеджера'
      }
      onClose={onClose}
      size="sm"
      dismissible={!mutation.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Скасувати
          </Button>
          <Button type="submit" form="warehouse-form" variant="save" disabled={mutation.isPending}>
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
      <form id="warehouse-form" className={styles.form} onSubmit={handleSubmit} noValidate>
        <Input
          label="Назва *"
          placeholder="Основний склад"
          value={form.name}
          onChange={(e) => update('name')(e.target.value)}
          error={errors.name}
          maxLength={150}
          autoFocus
        />
        <Input
          label="Адреса"
          placeholder="м. Харків, вул. Сумська, 12"
          value={form.address}
          onChange={(e) => update('address')(e.target.value)}
          error={errors.address}
          maxLength={500}
        />
        <Input
          label="Площа, м² *"
          inputMode="decimal"
          placeholder="1500"
          value={form.total_area}
          onChange={(e) => update('total_area')(e.target.value)}
          error={errors.total_area}
          hint="Загальна площа приміщення"
        />
        {serverError && (
          <p className={styles.serverError} role="alert">
            {serverError}
          </p>
        )}
      </form>
    </Modal>
  );
}
