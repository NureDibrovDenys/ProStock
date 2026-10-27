import { ApiError, request, setAccessToken } from './client';
import type { AuthUser, Session } from './types';

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

/** POST /api/v1/auth/login — вхід; refresh-токен приходить у httpOnly cookie. */
export async function login(email: string, password: string): Promise<Session> {
  const data = await request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
  });
  setAccessToken(data.access_token);
  return { user: data.user, expiresAt: Date.now() + data.expires_in * 1000 };
}

/** POST /api/v1/auth/logout — відкликає refresh-токен на сервері. */
export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST', auth: false });
  } catch (error) {
    // Навіть якщо сервер недоступний, локальну сесію треба скинути
    if (!(error instanceof ApiError)) throw error;
  } finally {
    setAccessToken(null);
  }
}

/** GET /api/v1/auth/me — актуальний профіль (роль, права, статус). */
export const getProfile = () => request<AuthUser & { created_at: string }>('/auth/me');
