import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { login as loginRequest, logout as logoutRequest } from '../api/auth';
import {
  UNAUTHORIZED_EVENT,
  refreshAccessToken,
  setAccessToken,
  setSessionListener,
} from '../api/client';
import type { Permission, Session } from '../api/types';

type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthContextValue {
  status: AuthStatus;
  session: Session | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Чи має поточна роль указане право. */
  can: (permission: Permission) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const LOGOUT_REASON_KEY = 'prostock.logoutReason';
const CHANNEL_NAME = 'prostock-auth';

/** Оновлюємо access-токен за 60 с до завершення, щоб користувач не помітив паузи. */
const REFRESH_LEEWAY_MS = 60_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const channelRef = useRef<BroadcastChannel | null>(null);

  const applySession = useCallback((next: Session) => {
    setSession(next);
    setStatus('authenticated');
  }, []);

  const clearSession = useCallback((reason?: string) => {
    setAccessToken(null);
    setSession(null);
    setStatus('anonymous');
    if (reason) {
      try {
        sessionStorage.setItem(LOGOUT_REASON_KEY, reason);
      } catch {
        // sessionStorage може бути недоступний
      }
    }
  }, []);

  /** Вихід за ініціативою користувача: відкликає refresh-токен на сервері. */
  const logout = useCallback(async () => {
    await logoutRequest();
    clearSession();
    channelRef.current?.postMessage('logout');
    try {
      sessionStorage.removeItem(LOGOUT_REASON_KEY);
    } catch {
      // ignore
    }
  }, [clearSession]);

  // Фоновий refresh оновлює стан сесії
  useEffect(() => {
    setSessionListener(applySession);
    return () => setSessionListener(null);
  }, [applySession]);

  // Відновлення сесії після перезавантаження сторінки: refresh-cookie → новий access
  useEffect(() => {
    let alive = true;
    (async () => {
      const restored = await refreshAccessToken();
      if (!alive) return;
      if (restored) applySession(restored);
      else setStatus('anonymous');
    })();
    return () => {
      alive = false;
    };
  }, [applySession]);

  // Автоматичне оновлення перед завершенням access-токена
  useEffect(() => {
    if (!session) return;

    const delay = Math.max(1_000, session.expiresAt - REFRESH_LEEWAY_MS - Date.now());
    const timer = window.setTimeout(async () => {
      const refreshed = await refreshAccessToken();
      if (!refreshed) clearSession('session-expired');
    }, delay);
    return () => window.clearTimeout(timer);
  }, [session, clearSession]);

  // Після сну компʼютера/вкладки перевіряємо, чи сесія ще жива
  useEffect(() => {
    if (!session) return;
    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() >= session.expiresAt - 5_000) {
        void refreshAccessToken().then((refreshed) => {
          if (!refreshed) clearSession('session-expired');
        });
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [session, clearSession]);

  // 401 від бекенда (токен відкликано, користувача заблоковано)
  useEffect(() => {
    const onUnauthorized = () => clearSession('session-expired');
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [clearSession]);

  // Синхронізація виходу між вкладками
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return;
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channelRef.current = channel;
    channel.onmessage = (event) => {
      if (event.data === 'logout') clearSession();
    };
    return () => {
      channel.close();
      channelRef.current = null;
    };
  }, [clearSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const next = await loginRequest(email, password);
      applySession(next);
      channelRef.current?.postMessage('login');
    },
    [applySession],
  );

  const can = useCallback(
    (permission: Permission) => Boolean(session?.user.permissions?.[permission]),
    [session],
  );

  const value = useMemo(
    () => ({ status, session, login, logout, can }),
    [status, session, login, logout, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** Причина автоматичного виходу — для повідомлення на сторінці входу. */
export function consumeLogoutReason(): string | null {
  try {
    const reason = sessionStorage.getItem(LOGOUT_REASON_KEY);
    sessionStorage.removeItem(LOGOUT_REASON_KEY);
    return reason;
  } catch {
    return null;
  }
}
