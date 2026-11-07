import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader } from 'lucide-react';
import { useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import type { RoleName, User } from '../api/types';
import { ROLE_LABELS, createStorekeeper, createUser } from '../api/users';
import { getWarehouses } from '../api/warehouse';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { useCurrentWarehouse } from '../hooks/useCurrentWarehouse';
import { useWarehouseName } from '../hooks/useWarehouse';
import { validateEmail, validateNewPassword } from '../lib/validation';
import styles from './NewEmployeePage.module.css';

type FormState = {
  first_name: string;
  last_name: string;
  user_email: string;
  password: string;
  role: RoleName;
  warehouse_id: number;
};

type Errors = Partial<Record<keyof FormState, string>>;

const ASSIGNABLE_ROLES: RoleName[] = ['administrator', 'warehouse_manager', 'storekeeper'];

const ROLE_HINTS: Partial<Record<RoleName, string>> = {
  administrator: 'Повний доступ: товари, користувачі, імпорт та експорт.',
  warehouse_manager: 'Товари й імпорт, створення комірників свого складу.',
  storekeeper: 'Перегляд каталогу та експорт; змінювати товари не може.',
};

function validate(form: FormState): Errors {
  const errors: Errors = {};
  if (!form.first_name.trim()) errors.first_name = "Вкажіть ім'я";
  if (!form.last_name.trim()) errors.last_name = 'Вкажіть прізвище';

  const emailError = validateEmail(form.user_email);
  if (emailError) errors.user_email = emailError;

  const passwordError = validateNewPassword(form.password);
  if (passwordError) errors.password = passwordError;

  return errors;
}

const FORM_FIELDS = new Set<string>(['first_name', 'last_name', 'user_email', 'password', 'role', 'warehouse_id']);

/** Помилки валідації бекенду (422) → помилки конкретних полів форми. */
function fieldErrorsFrom(error: ApiError): Errors {
  const errors: Errors = {};
  for (const detail of error.details) {
    const field = detail.field === 'email' ? 'user_email' : detail.field;
    if (field && FORM_FIELDS.has(field)) errors[field as keyof FormState] = detail.message;
  }
  return errors;
}

const emptyForm = (warehouseId: number): FormState => ({
  first_name: '',
  last_name: '',
  user_email: '',
  password: '',
  role: 'storekeeper',
  warehouse_id: warehouseId,
});

/**
 * Створення облікового запису.
 * • Адміністратор: будь-яка роль і будь-який склад (POST /users).
 * • Менеджер складу: лише комірник, склад — власний, без вибору (POST /managers/storekeepers).
 */
export function NewEmployeePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can, session } = useAuth();
  const isManagerMode = !can('users_manage') && can('storekeepers_manage');
  // useCurrentWarehouse() підставляє склад №1 для профілів без складу — для менеджера це хибна підказка,
  // тому відсутність складу перевіряємо напряму за профілем.
  const managerWithoutWarehouse = isManagerMode && session?.user.warehouse_id == null;

  const defaultWarehouseId = useCurrentWarehouse();
  const ownWarehouseName = useWarehouseName();
  const warehousesQuery = useQuery({
    queryKey: ['warehouses'],
    queryFn: getWarehouses,
    enabled: !isManagerMode,
  });

  const [form, setForm] = useState<FormState>(() => emptyForm(defaultWarehouseId));
  const [errors, setErrors] = useState<Errors>({});

  const mutation = useMutation({
    mutationFn: (data: FormState): Promise<User> => {
      const base = {
        first_name: data.first_name.trim(),
        last_name: data.last_name.trim(),
        user_email: data.user_email.trim().toLowerCase(),
        password: data.password,
      };
      return isManagerMode
        ? createStorekeeper(base)
        : createUser({ ...base, role: data.role, warehouse_id: data.warehouse_id });
    },
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      const roleLabel = isManagerMode ? 'Комірника' : 'Співробітника';
      toast.success(`${roleLabel} ${user.first_name} ${user.last_name} створено`);
      if (isManagerMode) {
        // Списку комірників для менеджера ще немає — лишаємось на формі для наступного запису
        setForm(emptyForm(defaultWarehouseId));
        setErrors({});
      } else {
        navigate('/employees');
      }
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          setErrors((prev) => ({ ...prev, user_email: 'Користувач з такою поштою вже існує' }));
        } else if (error.status === 422) {
          setErrors((prev) => ({ ...prev, ...fieldErrorsFrom(error) }));
        }
      }
    },
  });

  const update = (field: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value as FormState[typeof field] }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
    mutation.reset();
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (mutation.isPending || managerWithoutWarehouse) return;
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    mutation.mutate(form);
  };

  // Загальна помилка під формою — для всього, що не прив'язано до конкретного поля
  const serverError = (() => {
    if (!mutation.isError) return null;
    const error = mutation.error;
    if (error instanceof ApiError) {
      if (error.status === 409) return null;
      if (error.status === 422 && Object.keys(fieldErrorsFrom(error)).length) return null;
      if (error.status === 403) {
        return isManagerMode
          ? 'Створювати комірників може лише менеджер, якому призначено склад. Зверніться до адміністратора.'
          : 'Недостатньо прав для створення облікового запису';
      }
      return error.message;
    }
    return isManagerMode ? 'Не вдалося створити комірника' : 'Не вдалося створити користувача';
  })();

  const role = isManagerMode ? 'storekeeper' : form.role;

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={handleSubmit} noValidate>
        <h1 className={styles.title}>{isManagerMode ? 'Новий комірник' : 'Новий співробітник'}</h1>
        <p className={styles.subtitle}>
          {isManagerMode
            ? 'Комірника буде автоматично призначено на ваш склад. Передайте йому пошту й тимчасовий пароль.'
            : 'Обліковий запис отримає доступ відповідно до обраної ролі. Передайте співробітнику пошту й тимчасовий пароль.'}
        </p>

        <div className={styles.nameRow}>
          <Input
            label="Ім'я *"
            placeholder="Іван"
            autoComplete="off"
            value={form.first_name}
            onChange={update('first_name')}
            error={errors.first_name}
            maxLength={100}
            autoFocus
          />
          <Input
            label="Прізвище *"
            placeholder="Петренко"
            autoComplete="off"
            value={form.last_name}
            onChange={update('last_name')}
            error={errors.last_name}
            maxLength={100}
          />
        </div>

        <Input
          label="Пошта *"
          type="email"
          placeholder="name@prostock.ua"
          autoComplete="off"
          value={form.user_email}
          onChange={update('user_email')}
          error={errors.user_email}
          maxLength={255}
        />

        <div className={styles.nameRow}>
          <Input
            label="Пароль *"
            type="password"
            placeholder="••••••••"
            autoComplete="new-password"
            value={form.password}
            onChange={update('password')}
            error={errors.password}
            hint="8+ символів, велика й мала літери, цифра"
          />
          {isManagerMode ? (
            <Input label="Роль" value={ROLE_LABELS.storekeeper} readOnly disabled />
          ) : (
            <Select label="Роль *" value={form.role} onChange={update('role')}>
              {ASSIGNABLE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </Select>
          )}
        </div>

        {isManagerMode ? (
          <Input
            label="Склад"
            value={managerWithoutWarehouse ? 'Не призначено' : ownWarehouseName}
            readOnly
            disabled
            error={
              managerWithoutWarehouse
                ? 'Вам ще не призначено склад — створювати комірників неможливо. Зверніться до адміністратора.'
                : undefined
            }
            hint="Комірник отримає доступ лише до вашого складу"
          />
        ) : (
          <Select
            label="Склад *"
            value={String(form.warehouse_id)}
            onChange={(event) => setForm((prev) => ({ ...prev, warehouse_id: Number(event.target.value) }))}
            disabled={warehousesQuery.isPending || warehousesQuery.isError}
          >
            {warehousesQuery.data?.map((warehouse) => (
              <option key={warehouse.warehouse_id} value={warehouse.warehouse_id}>
                {warehouse.warehouse_name}
              </option>
            ))}
            {!warehousesQuery.data?.length && <option value={defaultWarehouseId}>Склад №{defaultWarehouseId}</option>}
          </Select>
        )}

        <div className={styles.roleHint}>{ROLE_HINTS[role]}</div>

        {serverError && (
          <p className={styles.error} role="alert">
            {serverError}
          </p>
        )}

        <div className={styles.actions}>
          <Button type="submit" variant="save" disabled={mutation.isPending || managerWithoutWarehouse}>
            {mutation.isPending ? (
              <>
                <Loader size={17} className="spin" aria-hidden /> Збереження…
              </>
            ) : isManagerMode ? (
              'Створити комірника'
            ) : (
              'Зберегти'
            )}
          </Button>
          <Button variant="secondary" onClick={() => navigate(isManagerMode ? '/' : '/employees')}>
            Скасувати
          </Button>
        </div>
      </form>
    </div>
  );
}
