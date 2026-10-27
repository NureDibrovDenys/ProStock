import { ArrowRight, Eye, EyeOff, Loader, LockKeyhole, Package } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { consumeLogoutReason, useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { validateEmail, validateLoginPassword, type FieldErrors } from '../lib/validation';
import styles from './LoginPage.module.css';

export function LoginPage() {
  const { session, status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const reason = consumeLogoutReason();
    if (reason === 'session-expired') {
      setNotice('Сесія завершилася. Увійдіть знову, щоб продовжити роботу.');
    }
    emailRef.current?.focus();
  }, []);

  if (session) return <Navigate to={from} replace />;

  const validateField = (field: 'email' | 'password', value: string) => {
    const message = field === 'email' ? validateEmail(value) : validateLoginPassword(value);
    setErrors((prev) => ({ ...prev, [field]: message }));
    return !message;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);

    const nextErrors: FieldErrors = {
      email: validateEmail(email),
      password: validateLoginPassword(password),
    };
    setErrors(nextErrors);
    if (nextErrors.email || nextErrors.password) {
      setFormError('Перевірте виділені поля');
      return;
    }

    setSubmitting(true);
    try {
      await login(email.trim().toLowerCase(), password);
      navigate(from, { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) setFormError('Невірний email або пароль');
        else if (error.status === 403) setFormError('Обліковий запис заблоковано. Зверніться до адміністратора.');
        else if (error.status === 429) setFormError(error.message);
        else if (error.status === 422) {
          setErrors({ email: error.details[0]?.message, password: undefined });
          setFormError('Перевірте введені дані');
        } else setFormError(error.message);
      } else {
        setFormError('Не вдалося увійти. Спробуйте ще раз.');
      }
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.brand} aria-hidden>
        <Package size={48} />
        <span>ProStock</span>
      </div>

      <form className={styles.card} onSubmit={handleSubmit} noValidate aria-busy={submitting}>
        <div className={styles.header}>
          <span className={styles.icon} aria-hidden>
            <LockKeyhole size={22} />
          </span>
          <h1 className={styles.title}>Вхід до системи</h1>
          <p className={styles.subtitle}>Використайте робочу пошту та пароль</p>
        </div>

        {notice && (
          <p className={styles.notice} role="status">
            {notice}
          </p>
        )}

        <Input
          ref={emailRef}
          label="Пошта"
          type="email"
          name="email"
          inputMode="email"
          autoComplete="username"
          placeholder="name@prostock.ua"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
          }}
          onBlur={() => email && validateField('email', email)}
          error={errors.email}
          disabled={submitting}
          required
        />

        <div className={styles.passwordField}>
          <Input
            label="Пароль"
            type={showPassword ? 'text' : 'password'}
            name="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
            }}
            onBlur={() => password && validateField('password', password)}
            onKeyUp={(e) => setCapsLock(e.getModifierState?.('CapsLock') ?? false)}
            error={errors.password}
            disabled={submitting}
            required
          />
          <button
            type="button"
            className={styles.reveal}
            onClick={() => setShowPassword((value) => !value)}
            aria-label={showPassword ? 'Приховати пароль' : 'Показати пароль'}
            title={showPassword ? 'Приховати пароль' : 'Показати пароль'}
            tabIndex={0}
          >
            {showPassword ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
          </button>
        </div>

        {capsLock && <p className={styles.hint}>Увімкнено Caps Lock</p>}

        {formError && (
          <p className={styles.error} role="alert">
            {formError}
          </p>
        )}

        <Button type="submit" block disabled={submitting || status === 'loading'}>
          {submitting ? (
            <>
              <Loader size={18} className={styles.spin} aria-hidden /> Вхід…
            </>
          ) : (
            <>
              Увійти <ArrowRight size={18} aria-hidden />
            </>
          )}
        </Button>

        <p className={styles.footer}>
          Немає доступу? Зверніться до адміністратора складу — він створить обліковий запис.
        </p>
      </form>
    </div>
  );
}
