// Базовий HTTP-клієнт для REST API ProStock.

const API_PREFIX = '/api/v1';
const TOKEN_KEY = 'prostock.token';

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // localStorage може бути недоступний (приватний режим) — сесія житиме до перезавантаження
  }
}

/** Подія, на яку підписується AuthProvider, щоб розлогінити користувача після 401. */
export const UNAUTHORIZED_EVENT = 'prostock:unauthorized';

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | undefined>;
};

export async function request<T>(path: string, { method = 'GET', body, query }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = getStoredToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let url = API_PREFIX + path;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (value !== undefined) params.set(key, String(value));
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Сервер недоступний. Перевірте підключення до мережі.');
  }

  if (response.status === 401 && token) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response, method, path));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function readErrorMessage(response: Response, method: string, path: string): Promise<string> {
  let data: { detail?: unknown } | null = null;
  try {
    data = await response.json();
  } catch {
    // тіло відповіді не JSON
  }

  const detail = data?.detail;
  // FastAPI на невідомий маршрут відповідає {"detail": "Not Found"}
  if (response.status === 404 && (detail === 'Not Found' || detail === undefined)) {
    return `Ендпоінт ${method} ${API_PREFIX}${path.split('?')[0]} ще не реалізований на бекенді`;
  }
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  // Dev-проксі Vite відповідає 5xx без JSON, коли бекенд не запущений
  if (response.status >= 500 && data === null) return 'Бекенд недоступний — перевірте, що сервер запущений';
  return `Помилка сервера (${response.status})`;
}
