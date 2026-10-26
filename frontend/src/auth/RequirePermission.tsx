import { ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from './AuthContext';
import type { Permission } from '../api/types';

/**
 * Обмежує доступ до сторінки за правом ролі.
 * Ховає навігацію окремо (NavBar), а тут — захищає прямий перехід за URL.
 */
export function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const { can } = useAuth();

  if (!can(permission)) {
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

  return <>{children}</>;
}
