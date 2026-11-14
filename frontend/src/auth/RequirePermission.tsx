import { ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from './AuthContext';
import type { Permission } from '../api/types';
import { isAdminRole } from '../api/users';

/**
 * Обмежує доступ до сторінки за правом ролі.
 * Ховає навігацію окремо (NavBar), а тут — захищає прямий перехід за URL.
 * Якщо передано кілька прав, достатньо будь-якого з них.
 */
export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission | Permission[];
  children: ReactNode;
}) {
  const { can } = useAuth();
  const allowed = (Array.isArray(permission) ? permission : [permission]).some(can);

  return allowed ? <>{children}</> : <AccessDenied />;
}

/** Сторінки лише для root / administrator (окремого права для них бекенд не віддає). */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  return isAdminRole(session?.user.role) ? <>{children}</> : <AccessDenied />;
}

function AccessDenied() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 16,
        padding: '80px 16px',
        textAlign: 'center',
      }}
      role="alert"
    >
      <ShieldAlert size={40} color="var(--color-danger)" aria-hidden />
      <h1 style={{ fontSize: 24, fontWeight: 600 }}>Недостатньо прав</h1>
      <p style={{ color: 'var(--color-muted)', maxWidth: 420 }}>
        Ваша роль не має доступу до цього розділу. Зверніться до адміністратора, якщо потрібні
        додаткові права.
      </p>
      <Link to="/" style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
        Повернутися на головну
      </Link>
    </div>
  );
}
