import { useQuery } from '@tanstack/react-query';
import type { User } from '../api/types';
import { ROLE_LABELS, getUsers } from '../api/users';
import { Button } from '../components/Button';
import { Avatar, ErrorState, LoadingState, PageHeader, UserStatusBadge } from '../components/ui';
import { WAREHOUSE_ID } from '../config';
import styles from './EmployeesPage.module.css';

export function EmployeesPage() {
  const query = useQuery({
    queryKey: ['users', WAREHOUSE_ID],
    queryFn: () => getUsers({ warehouse_id: WAREHOUSE_ID, page_size: 100 }),
  });
  const users = query.data?.items ?? [];
  const active = users.filter((u) => u.status === 'active');

  return (
    <>
      <PageHeader
        title="Співробітники"
        subtitle={query.data ? `Усього ${query.data.total} · активних ${active.length}` : undefined}
        actions={<Button to="/employees/new">+ Додати співробітника</Button>}
      />

      {query.isPending && <LoadingState />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data && (
        <div className={styles.lists}>
          <section className={styles.onShift}>
            <h2 className={styles.onShiftTitle}>Активні облікові записи · {active.length}</h2>
            {active.length === 0 ? (
              <p className={styles.muted}>Немає активних користувачів</p>
            ) : (
              <ul className={styles.chips}>
                {active.map((u) => (
                  <li key={u.user_id} className={styles.chip}>
                    <Avatar firstName={u.first_name} lastName={u.last_name} size="sm" />
                    {u.first_name} {u.last_name}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={styles.all}>
            <h2 className={styles.allTitle}>Усі співробітники</h2>
            {users.length === 0 ? (
              <p className={styles.muted}>Співробітників ще немає — додайте першого.</p>
            ) : (
              <ul className={styles.rows}>
                {users.map((u) => (
                  <EmployeeRow key={u.user_id} user={u} />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}

function EmployeeRow({ user: u }: { user: User }) {
  return (
    <li className={styles.row}>
      <Avatar firstName={u.first_name} lastName={u.last_name} />
      <div className={styles.person}>
        <p className={styles.name}>
          {u.first_name} {u.last_name}
        </p>
        <p className={styles.email}>{u.user_email}</p>
      </div>
      <p className={styles.position}>{u.position ?? ROLE_LABELS[u.role] ?? u.role}</p>
      <UserStatusBadge status={u.status} />
    </li>
  );
}
