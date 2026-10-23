import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type ChangeEvent, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import type { NewUser } from '../api/types';
import { createUser } from '../api/users';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { WAREHOUSE_ID } from '../config';
import styles from './NewEmployeePage.module.css';

type FormState = Pick<NewUser, 'first_name' | 'last_name' | 'user_email' | 'password'>;
type Errors = Partial<Record<keyof FormState, string>>;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD = 8;

function validate(form: FormState): Errors {
  const errors: Errors = {};
  if (!form.first_name.trim()) errors.first_name = "Вкажіть ім'я";
  if (!form.last_name.trim()) errors.last_name = 'Вкажіть прізвище';
  if (!EMAIL_RE.test(form.user_email.trim())) errors.user_email = 'Некоректна адреса пошти';
  if (form.password.length < MIN_PASSWORD) errors.password = `Щонайменше ${MIN_PASSWORD} символів`;
  return errors;
}

export function NewEmployeePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>({ first_name: '', last_name: '', user_email: '', password: '' });
  const [errors, setErrors] = useState<Errors>({});

  const mutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      navigate('/employees');
    },
  });

  const update = (field: keyof FormState) => (e: ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    // Менеджер складу може створювати лише комірників свого складу (SRS, IR-4)
    mutation.mutate({
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      user_email: form.user_email.trim().toLowerCase(),
      password: form.password,
      role: 'storekeeper',
      warehouse_id: WAREHOUSE_ID,
    });
  };

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={handleSubmit} noValidate>
        <h1 className={styles.title}>Новий співробітник</h1>
        <p className={styles.subtitle}>Дані для входу співробітник отримає на вказану пошту</p>

        <div className={styles.nameRow}>
          <Input
            label="Ім'я"
            placeholder="Іван"
            autoComplete="off"
            value={form.first_name}
            onChange={update('first_name')}
            error={errors.first_name}
            autoFocus
          />
          <Input
            label="Прізвище"
            placeholder="Петренко"
            autoComplete="off"
            value={form.last_name}
            onChange={update('last_name')}
            error={errors.last_name}
          />
        </div>
        <Input
          label="Пошта"
          type="email"
          placeholder="name@prostock.ua"
          autoComplete="off"
          value={form.user_email}
          onChange={update('user_email')}
          error={errors.user_email}
        />
        <Input
          label="Пароль"
          type="password"
          placeholder="••••••••"
          autoComplete="new-password"
          value={form.password}
          onChange={update('password')}
          error={errors.password}
        />

        {mutation.isError && (
          <p className={styles.error} role="alert">
            {mutation.error.message}
          </p>
        )}

        <div className={styles.actions}>
          <Button type="submit" variant="save" disabled={mutation.isPending}>
            {mutation.isPending ? 'Збереження…' : 'Зберегти'}
          </Button>
          <Button variant="cancel" onClick={() => navigate('/employees')}>
            Скасувати
          </Button>
        </div>
      </form>
    </div>
  );
}
