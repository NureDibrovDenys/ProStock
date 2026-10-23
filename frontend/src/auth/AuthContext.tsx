import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { login as loginRequest, sessionFromToken } from '../api/auth';
import { UNAUTHORIZED_EVENT, getStoredToken, storeToken } from '../api/client';
import type { Session } from '../api/types';

interface AuthContextValue {
  session: Session | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function restoreSession(): Session | null {
  const token = getStoredToken();
  const session = token ? sessionFromToken(token) : null;
  if (token && !session) storeToken(null);
  return session;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(restoreSession);

  const logout = useCallback(() => {
    storeToken(null);
    setSession(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const next = await loginRequest(email, password);
    storeToken(next.token);
    setSession(next);
  }, []);

  // Бекенд відповів 401 — токен відкликано або прострочено
  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, logout);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, logout);
  }, [logout]);

  // Автоматичний вихід, коли спливає термін дії токена
  useEffect(() => {
    if (!session || !Number.isFinite(session.expiresAt)) return;
    // setTimeout не приймає затримки довші за ~24.8 доби
    const delay = Math.min(Math.max(0, session.expiresAt - Date.now()), 2 ** 31 - 1);
    const timeout = setTimeout(logout, delay);
    return () => clearTimeout(timeout);
  }, [session, logout]);

  const value = useMemo(() => ({ session, login, logout }), [session, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
