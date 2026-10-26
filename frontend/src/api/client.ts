// Базовий HTTP-клієнт для REST API ProStock.
//
// Безпека сесії:
// • access-токен зберігається ЛИШЕ в памʼяті модуля (не в localStorage) —
//   його не можна викрасти через XSS-скрипт і він зникає після перезавантаження;
// • refresh-токен живе в httpOnly cookie, недоступній для JS;
// • після 401 клієнт один раз пробує оновити access-токен і повторює запит.

import type { AuthUser, Session } from './types';

export const API_PREFIX = '/api/v1';

/** Подія: сесію втрачено, потрібен вихід на сторінку входу. */
export const UNAUTHORIZED_EVENT = 'prostock:unauthorized';

export interface ValidationDetail {
  field: string | null;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly details: ValidationDetail[];

  constructor(status: number, message: string, details: ValidationDetail[] = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

let accessToken: string | null = null;
let refreshInFlight: Promise<Session | null> | null = null;
let sessionListener: ((session: Session) => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** AuthProvider підписується, щоб оновити стан після фонового refresh. */
export function setSessionListener(listener: ((session: Session) => void) | null) {
  sessionListener = listener;
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  /** false — не додавати Authorization і не намагатися оновити токен (login/refresh). */
  auth?: boolean;
  signal?: AbortSignal;
};

function buildUrl(path: string, query?: RequestOptions['query']): string {
  let url = API_PREFIX + path;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  return url;
}

function authHeaders(useAuth: boolean): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (useAuth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return headers;
}

/**
 * Оновлює access-токен за httpOnly refresh-cookie.
 * Повертає нову сесію або null, якщо refresh-токен прострочений/відкликаний.
 * Одночасні виклики обʼєднуються в один запит.
 */
export async function refreshAccessToken(): Promise<Session | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_PREFIX}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        accessToken = null;
        return null;
      }
      const data = (await response.json()) as TokenResponse;
      accessToken = data.access_token;
      const session: Session = {
        user: data.user,
        expiresAt: Date.now() + data.expires_in * 1000,
      };
      sessionListener?.(session);
      return session;
    } catch {
      accessToken = null;
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function readError(response: Response, method: string, path: string): Promise<ApiError> {
  let data: { detail?: unknown } | null = null;
  try {
    data = await response.json();
  } catch {
    // тіло не JSON
  }

  const detail = data?.detail;
  const details: ValidationDetail[] = [];

  if (Array.isArray(detail)) {
    for (const item of detail as Array<{ loc?: Array<string | number>; msg?: string }>) {
      const loc = item.loc ?? [];
      const field = loc.length > 1 ? String(loc[loc.length - 1]) : null;
      details.push({ field, message: item.msg ?? 'Некоректне значення' });
    }
    if (details.length > 0) {
      return new ApiError(response.status, details[0].message, details);
    }
  }

  if (response.status === 404 && (detail === 'Not Found' || detail === undefined)) {
    return new ApiError(404, `Ендпоінт ${method} ${API_PREFIX}${path.split('?')[0]} ще не реалізований`);
  }
  if (typeof detail === 'string') return new ApiError(response.status, detail, details);
  if (response.status >= 500) {
    return new ApiError(response.status, 'Помилка сервера. Спробуйте пізніше.');
  }
  return new ApiError(response.status, `Помилка сервера (${response.status})`, details);
}

async function send(
  path: string,
  { method = 'GET', body, query, auth = true, signal }: RequestOptions,
): Promise<Response> {
  const headers = authHeaders(auth);
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  return fetch(buildUrl(path, query), {
    method,
    headers,
    credentials: 'include',
    signal,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true } = options;
  let response: Response;

  try {
    response = await send(path, options);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Сервер недоступний. Перевірте підключення до мережі.');
  }

  // Access-токен міг прострочитися — пробуємо тихо оновити сесію
  if (response.status === 401 && auth) {
    const session = await refreshAccessToken();
    if (session) {
      try {
        response = await send(path, options);
      } catch {
        throw new ApiError(0, 'Сервер недоступний. Перевірте підключення до мережі.');
      }
    } else {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
  }

  if (!response.ok) {
    throw await readError(response, options.method ?? 'GET', path);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Завантажує файл (експорт) з урахуванням авторизації та поновлення токена. */
export async function downloadFile(
  path: string,
  options: { query?: RequestOptions['query']; fallbackFilename: string },
): Promise<void> {
  let response: Response;
  try {
    response = await send(path, { query: options.query });
    if (response.status === 401) {
      const session = await refreshAccessToken();
      if (!session) {
        window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
        throw new ApiError(401, 'Сесія завершилася. Увійдіть знову.');
      }
      response = await send(path, { query: options.query });
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'Не вдалося завантажити файл');
  }

  if (!response.ok) throw await readError(response, 'GET', path);

  const blob = await response.blob();
  const filename = parseFilename(response.headers.get('Content-Disposition')) ?? options.fallbackFilename;

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Даємо браузеру час почати завантаження
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function parseFilename(header: string | null): string | null {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) return decodeURIComponent(utf8[1]);
  const simple = /filename="?([^";]+)"?/i.exec(header);
  return simple ? simple[1] : null;
}

/** Завантаження blob-файлу, згенерованого на клієнті (звіт про помилки імпорту). */
export function downloadBlob(content: BlobPart, filename: string, type = 'text/csv;charset=utf-8') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
