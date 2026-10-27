import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader } from 'lucide-react';
import { useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import type { RoleName } from '../api/types';
import { ROLE_LABELS, createUser } from '../api/users';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { Select } from '../components/Select';
import { WAREHOUSE_ID } from '../config';
import { validateEmail, validateNewPassword } from '../lib/validation';
import styles from './NewEmployeePage.module.css';

type FormState = {
  first_name: string;
  last_name: string;
  user_email: string;
  password: string;
  role: RoleName;
};

type Errors = Partial<Record<keyof FormState, string>>;

const ASSIGNABLE_ROLES: RoleName[] = ['administrator', 'warehouse_manager', 'storekeeper'];

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

export function NewEmployeePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>({
    first_name: '',
    last_name: '',
    user_email: '',
    password: '',
    role: 'storekeeper',
  });
  const [errors, setErrors] = useState<Errors>({});

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      navigate('/employees');
    },
  });

  const update = (field: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value as FormState[typeof field] }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
    mutation.reset();
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    mutation.mutate({
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      user_email: form.user_email.trim().toLowerCase(),
      password: form.password,
      role: form.role,
      warehouse_id: WAREHOUSE_ID,
    });
  };

  const serverError = (() => {
    if (!mutation.isError) return null;
    if (mutation.error instanceof ApiError) {
      if (mutation.error.status === 409) return 'Користувач з такою поштою вже існує';
      return mutation.error.message;
    }
    return 'Не вдалося створити користувача';
  })();

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={handleSubmit} noValidate>
        <h1 className={styles.title}>Новий співробітник</h1>
        <p className={styles.subtitle}>
          Обліковий запис отримає доступ відповідно до обраної ролі. Передайте співробітнику
          пошту й тимчасовий пароль.
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
          <Select label="Роль *" value={form.role} onChange={update('role')}>
            {ASSIGNABLE_ROLES.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </Select>
        </div>

        <div className={styles.roleHint}>
          {form.role === 'administrator' && 'Повний доступ: товари, користувачі, імпорт та експорт.'}
          {form.role === 'warehouse_manager' && 'Товари й імпорт, перегляд співробітників без керування.'}
          {form.role === 'storekeeper' && 'Перегляд каталогу та експорт; змінювати товари не може.'}
        </div>

        {serverError && (
          <p className={styles.error} role="alert">
            {serverError}
          </p>
        )}

        <div className={styles.actions}>
          <Button type="submit" variant="save" disabled={mutation.isPending}>
            {mutation.isPending ? (
              <>
                <Loader size={17} className="spin" aria-hidden /> Збереження…
              </>
            ) : (
              'Зберегти'
            )}
          </Button>
          <Button variant="secondary" onClick={() => navigate('/employees')}>
            Скасувати
          </Button>
        </div>
      </form>
    </div>
  );
}
