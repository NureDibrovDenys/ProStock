import { ApiError, request } from './client';
import type { Session } from './types';

interface TokenResponse {
  access_token: string;
  token_type: string;
}

/** POST /api/v1/auth/login — повертає JWT. */
export async function login(email: string, password: string): Promise<Session> {
  const { access_token } = await request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
  const session = sessionFromToken(access_token);
  if (!session) throw new ApiError(500, 'Сервер повернув некоректний токен');
  return session;
}

/** Розбирає payload JWT (без перевірки підпису — це робить бекенд). */
export function sessionFromToken(token: string): Session | null {
  try {
    const payload = JSON.parse(decodeBase64Url(token.split('.')[1]));
    const expiresAt = typeof payload.exp === 'number' ? payload.exp * 1000 : Number.POSITIVE_INFINITY;
    if (expiresAt <= Date.now()) return null;
    return { token, email: payload.sub ?? '', role: payload.role ?? '', expiresAt };
  } catch {
    return null;
  }
}

function decodeBase64Url(value: string): string {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}
