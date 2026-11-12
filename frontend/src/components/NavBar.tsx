import { LogOut, Package, Users, Warehouse } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import type { Permission } from '../api/types';
import { ROLE_LABELS } from '../api/users';
import { useAuth } from '../auth/AuthContext';
import { cx } from '../lib/cx';
import { WarehouseSwitcher } from './WarehouseSwitcher';
import styles from './NavBar.module.css';

/** Вкладка видима, якщо є хоча б одне з прав (null — для всіх). */
type Tab = { to: string; label: string; end: boolean; permission: Permission[] | null };

const TABS: Tab[] = [
  { to: '/products', label: 'Товари', end: false, permission: ['products_read'] },
  // Адміністратор бачить усіх співробітників, менеджер складу — комірників свого складу
  { to: '/employees', label: 'Співробітники', end: false, permission: ['users_manage', 'storekeepers_manage'] },
  { to: '/warehouse', label: 'Склад', end: false, permission: null },
];

export function NavBar() {
  const { session, logout, can } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const visibleTabs = TABS.filter((tab) => !tab.permission || tab.permission.some(can));
  const user = session?.user;

  return (
    <header className={styles.bar}>
      <NavLink to="/" className={styles.logo}>
        <Package size={24} aria-hidden />
        ProStock
      </NavLink>
      <nav className={styles.tabs} aria-label="Головна навігація">
        {visibleTabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => cx(styles.tab, isActive && styles.active)}
          >
            {tab.to === '/employees' && <Users size={16} aria-hidden />}
            {tab.to === '/warehouse' && <Warehouse size={16} aria-hidden />}
            {tab.to === '/products' && <Package size={16} aria-hidden />}
            {tab.label}
          </NavLink>
        ))}
      </nav>
      {/* Адміністратор перемикає поточний склад; решта ролей працює зі своїм */}
      <WarehouseSwitcher />
      <div className={styles.spacer} />
      {user ? (
        <div className={styles.user}>
          <div className={styles.userInfo}>
            <span className={styles.userName}>
              {user.first_name} {user.last_name}
            </span>
            <span className={styles.userRole}>{ROLE_LABELS[user.role] ?? user.role}</span>
          </div>
          <button
            type="button"
            className={styles.logout}
            onClick={handleLogout}
            title="Вийти з облікового запису"
            aria-label="Вийти з облікового запису"
          >
            <LogOut size={18} aria-hidden />
          </button>
        </div>
      ) : (
        <NavLink to="/login" className={styles.tab}>
          Увійти
        </NavLink>
      )}
    </header>
  );
}
