import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader } from 'lucide-react';
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import type { NewStorekeeper, RoleName, User } from '../api/types';
import { ROLE_LABELS, createStorekeeper, createUser, getStorekeeper, updateStorekeeper } from '../api/users';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { WarehouseFormModal } from '../components/WarehouseFormModal';
import { ErrorState, LoadingState } from '../components/ui';
import { useCurrentWarehouse, useWarehouses } from '../hooks/useCurrentWarehouse';
import { useWarehouseName } from '../hooks/useWarehouse';
import { validateEmail, validateNewPassword } from '../lib/validation';
import styles from './NewEmployeePage.module.css';

type FormState = {
  first_name: string;
  last_name: string;
  user_email: string;
  password: string;
  role: RoleName;
  warehouse_id: number | null;
};

type Errors = Partial<Record<keyof FormState, string>>;

const ASSIGNABLE_ROLES: RoleName[] = ['administrator', 'warehouse_manager', 'storekeeper'];

const ROLE_HINTS: Partial<Record<RoleName, string>> = {
  administrator: 'Повний доступ: товари, користувачі, імпорт та експорт.',
  warehouse_manager: 'Товари й імпорт, створення комірників свого складу.',
  storekeeper: 'Перегляд каталогу та експорт; змінювати товари не може.',
};

/** Адміністратор не прив'язується до складу; комірник без складу працювати не може (бекенд відхилить). */
const roleUsesWarehouse = (role: RoleName) => role !== 'administrator' && role !== 'root';

/** passwordOptional — під час редагування порожній пароль означає «не змінювати». */
function validate(form: FormState, { passwordOptional = false, chooseWarehouse = false } = {}): Errors {
  const errors: Errors = {};
  if (chooseWarehouse && form.role === 'storekeeper' && form.warehouse_id === null) {
    errors.warehouse_id = 'Комірника потрібно призначити на склад';
  }
  if (!form.first_name.trim()) errors.first_name = "Вкажіть ім'я";
  if (!form.last_name.trim()) errors.last_name = 'Вкажіть прізвище';

  const emailError = validateEmail(form.user_email);
  if (emailError) errors.user_email = emailError;

  if (!(passwordOptional && form.password === '')) {
    const passwordError = validateNewPassword(form.password);
    if (passwordError) errors.password = passwordError;
  }

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

const emptyForm = (warehouseId: number | null): FormState => ({
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
 * • Редагування комірника менеджером (/employees/:userId/edit): ім'я, прізвище, пошта, пароль
 *   (PATCH /managers/storekeepers/{id}); роль і склад не змінюються.
 */
export function NewEmployeePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can, session } = useAuth();
  const { userId } = useParams();
  const editId = userId ? Number(userId) : null;
  const isEdit = editId !== null;
  const isManagerMode = isEdit || (!can('users_manage') && can('storekeepers_manage'));
  // Менеджер без призначеного складу не може керувати комірниками.
  // тому відсутність складу перевіряємо напряму за профілем.
  const managerWithoutWarehouse = isManagerMode && session?.user.warehouse_id == null;

  const defaultWarehouseId = useCurrentWarehouse();
  const ownWarehouseName = useWarehouseName();
  const warehousesQuery = useWarehouses(!isManagerMode);
  const [creatingWarehouse, setCreatingWarehouse] = useState(false);

  const [form, setForm] = useState<FormState>(() => emptyForm(defaultWarehouseId));
  const [errors, setErrors] = useState<Errors>({});

  // Адміністратор: за замовчуванням — поточний склад із перемикача (список складів може прийти пізніше)
  const warehouseTouched = useRef(false);
  useEffect(() => {
    if (!isManagerMode && !warehouseTouched.current && defaultWarehouseId !== null) {
      setForm((prev) => (prev.warehouse_id === null ? { ...prev, warehouse_id: defaultWarehouseId } : prev));
    }
  }, [isManagerMode, defaultWarehouseId]);

  const chooseWarehouse = (warehouseId: number | null) => {
    warehouseTouched.current = true;
    setForm((prev) => ({ ...prev, warehouse_id: warehouseId }));
    setErrors((prev) => ({ ...prev, warehouse_id: undefined }));
    mutation.reset();
  };

  const storekeeperQuery = useQuery({
    queryKey: ['users', 'storekeeper', editId],
    queryFn: () => getStorekeeper(editId as number),
    enabled: isEdit,
  });
  const original = storekeeperQuery.data;

  // Заповнюємо форму даними комірника один раз — повторні запити не мають затирати введене
  const prefilledFor = useRef<number | null>(null);
  useEffect(() => {
    if (original && prefilledFor.current !== original.user_id) {
      prefilledFor.current = original.user_id;
      setForm((prev) => ({
        ...prev,
        first_name: original.first_name,
        last_name: original.last_name,
        user_email: original.user_email,
        password: '',
      }));
    }
  }, [original]);

  /** Лише змінені поля: PATCH не повинен перезаписувати те, чого менеджер не чіпав. */
  const changesFrom = (data: FormState): Partial<NewStorekeeper> => {
    const next = {
      first_name: data.first_name.trim(),
      last_name: data.last_name.trim(),
      user_email: data.user_email.trim().toLowerCase(),
    };
    const changes: Partial<NewStorekeeper> = {};
    if (next.first_name !== original?.first_name) changes.first_name = next.first_name;
    if (next.last_name !== original?.last_name) changes.last_name = next.last_name;
    if (next.user_email !== original?.user_email) changes.user_email = next.user_email;
    if (data.password) changes.password = data.password;
    return changes;
  };

  const mutation = useMutation({
    mutationFn: (data: FormState): Promise<User> => {
      if (isEdit) return updateStorekeeper(editId as number, changesFrom(data));
      const base = {
        first_name: data.first_name.trim(),
        last_name: data.last_name.trim(),
        user_email: data.user_email.trim().toLowerCase(),
        password: data.password,
      };
      return isManagerMode
        ? createStorekeeper(base)
        : createUser({ ...base, role: data.role, warehouse_id: roleUsesWarehouse(data.role) ? data.warehouse_id : null });
    },
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      if (isEdit) {
        toast.success(`Дані комірника ${user.first_name} ${user.last_name} оновлено`);
      } else {
        const roleLabel = isManagerMode ? 'Комірника' : 'Співробітника';
        toast.success(`${roleLabel} ${user.first_name} ${user.last_name} створено`);
      }
      navigate('/employees');
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
    const nextErrors = validate(form, { passwordOptional: isEdit, chooseWarehouse: !isManagerMode });
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    if (isEdit && Object.keys(changesFrom(form)).length === 0) {
      toast.info('Змін немає — нічого зберігати');
      return;
    }
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
          ? 'Керувати комірниками може лише менеджер, якому призначено склад. Зверніться до адміністратора.'
          : 'Недостатньо прав для створення облікового запису';
      }
      if (error.status === 404 && isEdit) return 'Комірника не знайдено на вашому складі';
      return error.message;
    }
    if (isEdit) return 'Не вдалося зберегти зміни';
    return isManagerMode ? 'Не вдалося створити комірника' : 'Не вдалося створити користувача';
  })();

  if (isEdit && storekeeperQuery.isPending) return <LoadingState />;
  if (isEdit && storekeeperQuery.isError) {
    return <ErrorState error={storekeeperQuery.error} onRetry={() => storekeeperQuery.refetch()} />;
  }

  const role = isManagerMode ? 'storekeeper' : form.role;

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={handleSubmit} noValidate>
        <h1 className={styles.title}>
          {isEdit ? 'Редагування комірника' : isManagerMode ? 'Новий комірник' : 'Новий співробітник'}
        </h1>
        <p className={styles.subtitle}>
          {isEdit
            ? "Можна змінити ім'я, прізвище, пошту та пароль. Роль і склад змінює адміністратор."
            : isManagerMode
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
            label={isEdit ? 'Новий пароль' : 'Пароль *'}
            type="password"
            placeholder={isEdit ? 'Не змінювати' : '••••••••'}
            autoComplete="new-password"
            value={form.password}
            onChange={update('password')}
            error={errors.password}
            hint={
              isEdit
                ? 'Залиште порожнім, щоб не змінювати. 8+ символів, велика й мала літери, цифра'
                : '8+ символів, велика й мала літери, цифра'
            }
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
        ) : roleUsesWarehouse(form.role) ? (
          <div className={styles.warehouseField}>
            <Select
              label={form.role === 'storekeeper' ? 'Склад *' : 'Склад'}
              value={form.warehouse_id === null ? '' : String(form.warehouse_id)}
              onChange={(event) => chooseWarehouse(event.target.value === '' ? null : Number(event.target.value))}
              disabled={warehousesQuery.isPending || warehousesQuery.isError}
              error={errors.warehouse_id}
            >
              {/* Менеджера можна призначити пізніше; комірник без складу не працює */}
              <option value="" disabled={form.role === 'storekeeper'}>
                {warehousesQuery.isPending ? 'Завантаження…' : form.role === 'storekeeper' ? 'Оберіть склад' : 'Без складу'}
              </option>
              {warehousesQuery.data?.map((warehouse) => (
                <option key={warehouse.warehouse_id} value={String(warehouse.warehouse_id)}>
                  {warehouse.warehouse_name}
                </option>
              ))}
            </Select>
            <button type="button" className={styles.newWarehouse} onClick={() => setCreatingWarehouse(true)}>
              + Новий склад
            </button>
            {warehousesQuery.data?.length === 0 && (
              <p className={styles.warehouseHint}>Складів ще немає — створіть перший, щоб призначити на нього співробітника.</p>
            )}
          </div>
        ) : (
          <Input label="Склад" value="Усі склади" readOnly disabled hint="Адміністратор не прив'язаний до складу" />
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
            ) : isEdit ? (
              'Зберегти зміни'
            ) : isManagerMode ? (
              'Створити комірника'
            ) : (
              'Зберегти'
            )}
          </Button>
          <Button variant="secondary" onClick={() => navigate('/employees')}>
            Скасувати
          </Button>
        </div>
      </form>
      {/* Поза формою співробітника: submit модалки не повинен відправляти її */}
      {creatingWarehouse && (
        <WarehouseFormModal
          onClose={() => setCreatingWarehouse(false)}
          onSaved={(saved) => chooseWarehouse(saved.warehouse_id)}
        />
      )}
    </div>
  );
}
