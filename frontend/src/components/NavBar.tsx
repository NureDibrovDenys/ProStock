import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { cx } from '../lib/cx';
import styles from './NavBar.module.css';

const TABS = [
  { to: '/', label: 'Головна', end: true },
  { to: '/employees', label: 'Співробітники', end: false },
  { to: '/warehouse', label: 'Склад', end: false },
];

export function NavBar() {
  const { session, logout } = useAuth();
  const navigate = useNavigate();

  const handleAuthClick = () => {
    if (session) logout();
    navigate('/login');
  };

  return (
    <header className={styles.bar}>
      <NavLink to="/" className={styles.logo}>
        ProStock
      </NavLink>
      <nav className={styles.tabs} aria-label="Головна навігація">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => cx(styles.tab, isActive && styles.active)}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className={styles.spacer} />
      <button
        type="button"
        className={styles.tab}
        onClick={handleAuthClick}
        title={session ? `Вийти (${session.email})` : 'Увійти'}
      >
        Вхід/Вихід
      </button>
    </header>
  );
}
