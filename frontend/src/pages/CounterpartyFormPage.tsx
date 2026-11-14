import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader } from 'lucide-react';
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import {
  DIRECTORY_LABELS,
  createCounterparty,
  getCounterparty,
  isCounterpartyKind,
  updateCounterparty,
} from '../api/directories';
import type { Counterparty, CounterpartyInput, CounterpartyKind } from '../api/types';
import { Button } from '../components/Button';
import { Input } from '../components/Input';
import { ErrorState, LoadingState } from '../components/ui';
import { EMAIL_PATTERN } from '../lib/validation';
import styles from './NewEmployeePage.module.css';

type FormState = {
  company_name: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  address: string;
  tax_id: string;
};

type Errors = Partial<Record<keyof FormState, string>>;

const EMPTY_FORM: FormState = {
  company_name: '',
  first_name: '',
  last_name: '',
  email: '',
  phone_number: '',
  address: '',
  tax_id: '',
};

const MAX = { company_name: 255, contact_person: 150, email: 100, phone_number: 30, tax_id: 20 };
const PHONE_PATTERN = /^\+?[\d\s()-]+$/;

function validate(form: FormState, kind: CounterpartyKind): Errors {
  const errors: Errors = {};
  const company = form.company_name.trim();
  if (!company) errors.company_name = 'Вкажіть назву';
  else if (company.length > MAX.company_name) errors.company_name = 'Назва занадто довга';

  if (`${form.first_name.trim()} ${form.last_name.trim()}`.trim().length > MAX.contact_person) {
    errors.last_name = "Ім'я та прізвище разом — не більше 150 символів";
  }

  const email = form.email.trim();
  if (email && (email.length > MAX.email || !EMAIL_PATTERN.test(email))) {
    errors.email = 'Некоректна пошта, наприклад name@company.ua';
  }

  const phone = form.phone_number.trim();
  const digits = phone.replace(/\D/g, '');
  if (phone && (!PHONE_PATTERN.test(phone) || digits.length < 10 || digits.length > 13 || phone.length > MAX.phone_number)) {
    errors.phone_number = 'Некоректний номер, наприклад +380 67 123 45 67';
  }

  if (kind === 'recipients' && !form.address.trim()) {
    errors.address = 'Вкажіть адресу доставки — без неї неможливо відвантажити товар';
  }

  const taxId = form.tax_id.trim();
  if (taxId && !/^(\d{8}|\d{10})$/.test(taxId)) {
    errors.tax_id = 'ЄДРПОУ — 8 цифр, ІПН — 10 цифр';
  }
  return errors;
}

/** Empty optional fields are stored as null */
function toInput(form: FormState): CounterpartyInput {
  const orNull = (value: string) => value.trim() || null;
  return {
    company_name: form.company_name.trim(),
    contact_person: orNull(`${form.first_name.trim()} ${form.last_name.trim()}`),
    email: orNull(form.email.toLowerCase()),
    phone_number: orNull(form.phone_number),
    address: orNull(form.address),
    tax_id: orNull(form.tax_id),
  };
}

/** In the model, the contact person is a single field; in the form (as shown in the mockup), the first name and last name are separate */
function toForm(item: Counterparty): FormState {
  const [first_name = '', ...rest] = (item.contact_person ?? '').split(' ');
  return {
    company_name: item.company_name,
    first_name,
    last_name: rest.join(' '),
    email: item.email ?? '',
    phone_number: item.phone_number ?? '',
    address: item.address ?? '',
    tax_id: item.tax_id ?? '',
  };
}

/** Only modified fields: PATCH should not overwrite anything the user hasn't touched */
function changesFrom(form: FormState, original: Counterparty): Partial<CounterpartyInput> {
  const next = toInput(form);
  const changes: Partial<CounterpartyInput> = {};
  for (const key of Object.keys(next) as Array<keyof CounterpartyInput>) {
    if (next[key] !== original[key]) Object.assign(changes, { [key]: next[key] });
  }
  return changes;
}

/** Creating (/directories/:kind/new) and editing (/directories/:kind/:id/edit) */
export function CounterpartyFormPage() {
  const { kind, id } = useParams();
  if (!isCounterpartyKind(kind)) return <Navigate to="/directories/suppliers" replace />;
  return <CounterpartyForm key={`${kind}-${id ?? 'new'}`} kind={kind} editId={id ? Number(id) : null} />;
}

function CounterpartyForm({ kind, editId }: { kind: CounterpartyKind; editId: number | null }) {
  const labels = DIRECTORY_LABELS[kind];
  const isEdit = editId !== null;
  const listPath = `/directories/${kind}`;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Errors>({});

  const itemQuery = useQuery({
    queryKey: ['directories', kind, editId],
    queryFn: () => getCounterparty(kind, editId as number),
    enabled: isEdit,
  });
  const original = itemQuery.data;

  //Fill out the form once — subsequent requests should not overwrite the entered data
  const prefilledFor = useRef<number | null>(null);
  useEffect(() => {
    if (original && prefilledFor.current !== original.id) {
      prefilledFor.current = original.id;
      setForm(toForm(original));
    }
  }, [original]);

  const mutation = useMutation({
    mutationFn: (data: FormState) =>
      isEdit && original
        ? updateCounterparty(kind, original.id, changesFrom(data, original))
        : createCounterparty(kind, toInput(data)),
    onSuccess: (item) => {
      void queryClient.invalidateQueries({ queryKey: ['directories', kind] });
      toast.success(`${labels.one} ${item.company_name} ${isEdit ? 'оновлено' : 'доданий до довідника'}`);
      navigate(listPath);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setErrors((prev) => ({ ...prev, tax_id: error.message }));
      }
    },
  });

  const update = (field: keyof FormState) => (event: ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
    mutation.reset();
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (mutation.isPending) return;
    const nextErrors = validate(form, kind);
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    if (isEdit && original && Object.keys(changesFrom(form, original)).length === 0) {
      toast.info('Змін немає — нічого зберігати');
      return;
    }
    mutation.mutate(form);
  };

  const serverError =
    mutation.isError && !(mutation.error instanceof ApiError && mutation.error.status === 409)
      ? mutation.error instanceof ApiError
        ? mutation.error.message
        : 'Не вдалося зберегти'
      : null;

  if (isEdit && itemQuery.isPending) return <LoadingState />;
  if (isEdit && itemQuery.isError) return <ErrorState error={itemQuery.error} onRetry={() => itemQuery.refetch()} />;

  const isRecipient = kind === 'recipients';

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={handleSubmit} noValidate>
        <h1 className={styles.title}>
          {isEdit ? `Редагування: ${original?.company_name}` : `Новий ${labels.one.toLowerCase()}`}
        </h1>

        <Input
          label={`${labels.nameLabel} *`}
          placeholder={labels.namePlaceholder}
          autoComplete="off"
          value={form.company_name}
          onChange={update('company_name')}
          error={errors.company_name}
          maxLength={MAX.company_name}
          autoFocus
        />

        <p className={styles.subtitle}>Контактна особа</p>
        <div className={styles.nameRow}>
          <Input
            label="Ім'я"
            placeholder="Іван"
            autoComplete="off"
            value={form.first_name}
            onChange={update('first_name')}
            error={errors.first_name}
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
          placeholder={isRecipient ? 'name@recipient.ua' : 'name@company.ua'}
          autoComplete="off"
          value={form.email}
          onChange={update('email')}
          error={errors.email}
          maxLength={MAX.email}
        />

        <Input
          label="Телефон"
          type="tel"
          placeholder="+380-xx-xxx-xx-xx"
          autoComplete="off"
          value={form.phone_number}
          onChange={update('phone_number')}
          error={errors.phone_number}
          maxLength={MAX.phone_number}
        />

        <Input
          label={isRecipient ? 'Адреса доставки *' : 'Адреса'}
          placeholder="м. Київ, вул. Промислова, 12"
          autoComplete="off"
          value={form.address}
          onChange={update('address')}
          error={errors.address}
        />

        <Input
          label="ЄДРПОУ / ІПН"
          placeholder="12345678"
          inputMode="numeric"
          autoComplete="off"
          value={form.tax_id}
          onChange={update('tax_id')}
          error={errors.tax_id}
          maxLength={MAX.tax_id}
          hint="ЄДРПОУ — 8 цифр, ІПН — 10 цифр"
        />

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
          <Button variant="cancel" onClick={() => navigate(listPath)}>
            Скасувати
          </Button>
        </div>
      </form>
    </div>
  );
}
