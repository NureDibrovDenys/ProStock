import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { ApiError } from '../api/client';
import type { User, UserStatus } from '../api/types';
import { ROLE_LABELS, getStorekeepers, getUsers, updateUser } from '../api/users';
import { Button } from '../components/Button';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { Avatar, ErrorState, LoadingState, PageHeader, UserStatusBadge } from '../components/ui';
import { useAuth } from '../auth/AuthContext';
import { useCurrentWarehouse } from '../hooks/useCurrentWarehouse';
import styles from './EmployeesPage.module.css';

export function EmployeesPage() {
  const { session, can } = useAuth();
  const queryClient = useQueryClient();
  const [pendingUser, setPendingUser] = useState<User | null>(null);
  const warehouseId = useCurrentWarehouse();
  // Менеджер складу бачить і редагує лише комірників свого складу
  const isManagerMode = !can('users_manage') && can('storekeepers_manage');
  const query = useQuery({
    queryKey: ['users', isManagerMode ? 'storekeepers' : warehouseId],
    queryFn: () =>
      isManagerMode ? getStorekeepers({ page_size: 100 }) : getUsers({ warehouse_id: warehouseId, page_size: 100 }),
  });
  const users = query.data?.items ?? [];
  const active = users.filter((u) => u.status === 'active');
  const statusMutation = useMutation({
    mutationFn: ({ userId, status }: { userId: number; status: UserStatus }) =>
      updateUser(userId, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      setPendingUser(null);
    },
  });
  const canManageUsers = can('users_manage');

  return (
    <>
      <PageHeader
        title={isManagerMode ? 'Комірники складу' : 'Співробітники'}
        subtitle={query.data ? `Усього ${query.data.total} · активних ${active.length}` : undefined}
        actions={<Button to="/employees/new">{isManagerMode ? '+ Додати комірника' : '+ Додати співробітника'}</Button>}
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
                  <EmployeeRow
                    key={u.user_id}
                    user={u}
                    canManageUsers={canManageUsers}
                    canEdit={isManagerMode}
                    isCurrentUser={u.user_id === session?.user.user_id}
                    onToggleStatus={setPendingUser}
                  />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
      {pendingUser && (
        <ConfirmDialog
          title={pendingUser.status === 'active' ? 'Деактивувати обліковий запис?' : 'Активувати обліковий запис?'}
          message={`${pendingUser.first_name} ${pendingUser.last_name}`}
          details={
            pendingUser.status === 'active'
              ? 'Користувач не зможе увійти до системи, доки обліковий запис не буде активовано.'
              : 'Користувач знову отримає доступ до системи.'
          }
          confirmLabel={pendingUser.status === 'active' ? 'Деактивувати' : 'Активувати'}
          busyLabel="Збереження…"
          busy={statusMutation.isPending}
          error={
            statusMutation.error instanceof ApiError
              ? statusMutation.error.message
              : statusMutation.isError
                ? 'Не вдалося змінити статус облікового запису'
                : null
          }
          onClose={() => {
            if (!statusMutation.isPending) {
              statusMutation.reset();
              setPendingUser(null);
            }
          }}
          onConfirm={() =>
            statusMutation.mutate({
              userId: pendingUser.user_id,
              status: pendingUser.status === 'active' ? 'inactive' : 'active',
            })
          }
        />
      )}
    </>
  );
}

function EmployeeRow({
  user: u,
  canManageUsers,
  canEdit,
  isCurrentUser,
  onToggleStatus,
}: {
  user: User;
  canManageUsers: boolean;
  canEdit: boolean;
  isCurrentUser: boolean;
  onToggleStatus: (user: User) => void;
}) {
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
      {canEdit && (
        <Button variant="secondary" className={styles.statusAction} to={`/employees/${u.user_id}/edit`}>
          Редагувати
        </Button>
      )}
      {canManageUsers && !isCurrentUser && (
        <Button
          variant="secondary"
          className={styles.statusAction}
          onClick={() => onToggleStatus(u)}
          aria-label={`${u.status === 'active' ? 'Деактивувати' : 'Активувати'} ${u.first_name} ${u.last_name}`}
        >
          {u.status === 'active' ? 'Вимкнути' : 'Увімкнути'}
        </Button>
      )}
    </li>
  );
}
