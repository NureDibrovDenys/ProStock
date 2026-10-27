/** Спільні правила валідації форм (дзеркалять обмеження бекенда). */

export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/;
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 128;
export const MAX_PASSWORD_BYTES = 72;

export interface FieldErrors {
  [field: string]: string | undefined;
}

export function validateEmail(value: string): string | undefined {
  const email = value.trim();
  if (!email) return 'Вкажіть адресу електронної пошти';
  if (email.length > 255) return 'Адреса занадто довга';
  if (!EMAIL_PATTERN.test(email)) return 'Некоректний формат пошти, наприклад name@prostock.ua';
  return undefined;
}

export function validateLoginPassword(value: string): string | undefined {
  if (!value) return 'Введіть пароль';
  if (value.length < MIN_PASSWORD_LENGTH) return `Пароль має містити щонайменше ${MIN_PASSWORD_LENGTH} символів`;
  if (value.length > MAX_PASSWORD_LENGTH) return `Пароль має містити не більше ${MAX_PASSWORD_LENGTH} символів`;
  if (new TextEncoder().encode(value).length > MAX_PASSWORD_BYTES) return 'Пароль занадто довгий';
  return undefined;
}

export function validateNewPassword(value: string): string | undefined {
  const basic = validateLoginPassword(value);
  if (basic) return basic;
  if (!/[A-ZА-ЯЇІЄҐ]/.test(value)) return 'Додайте хоча б одну велику літеру';
  if (!/[a-zа-яїієґ]/.test(value)) return 'Додайте хоча б одну малу літеру';
  if (!/\d/.test(value)) return 'Додайте хоча б одну цифру';
  return undefined;
}

/** Додає серверні помилки валідації (FastAPI `detail[].loc`) до помилок полів. */
export function mapServerErrors(
  details: Array<{ field: string | null; message: string }>,
  knownFields: string[],
): FieldErrors {
  const errors: FieldErrors = {};
  for (const detail of details) {
    const field = detail.field && knownFields.includes(detail.field) ? detail.field : undefined;
    if (field && !errors[field]) errors[field] = detail.message;
  }
  return errors;
}
