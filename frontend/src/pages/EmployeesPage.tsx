import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { ApiError } from '../api/client';
import type { User, UserStatus } from '../api/types';
import { ROLE_LABELS, getUsers, updateUser } from '../api/users';
import { Button } from '../components/Button';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { Avatar, ErrorState, LoadingState, PageHeader, UserStatusBadge } from '../components/ui';
import { useAuth } from '../auth/AuthContext';
import { getWarehouses } from '../api/warehouse';
import { Select } from '../components/Select';

import styles from './EmployeesPage.module.css';
import { AssignWarehouseModal } from '../components/AssignWarehouseModal';


export function EmployeesPage() {
  const { session, can } = useAuth();
  const queryClient = useQueryClient();
  const [pendingUser, setPendingUser] = useState<User | null>(null);
  /**стан фіальта та запит складів */
  const [warehouseFilter, setWarehouseFilter] = useState('');
  const warehousesQuery = useQuery({
    queryKey: ['warehouses'],
    queryFn: getWarehouses,
  });
  const warehouses = warehousesQuery.data ?? [];

  const [assignmentUser, setAssignmentUser] = useState<User | null>(null);

  const query = useQuery({
    queryKey: ['users', warehouseFilter],
    queryFn: () => getUsers({ page_size: 100, warehouse_id: warehouseFilter === '' ? undefined : Number(warehouseFilter) }),
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
        title="Співробітники"
        subtitle={query.data ? `Усього ${query.data.total} · активних ${active.length}` : undefined}
        actions={<Button to="/employees/new">+ Додати співробітника</Button>}
      />
      
      <div className={styles.filters}>
        <Select
          label="Фільтр за складом"
          value={warehouseFilter}
          onChange={(event) => setWarehouseFilter(event.target.value)}
          disabled={!warehousesQuery.isSuccess}
        >
          <option value="">Усі склади</option>

          {warehouses.map((warehouse) => (
            <option
              key={warehouse.warehouse_id}
              value={String(warehouse.warehouse_id)}>
              {warehouse.warehouse_name}
            </option>
          ))}
        </Select>
      </div>
      {warehousesQuery.isPending && (
        <LoadingState label="Завантаження складів..." />
      )}
      {warehousesQuery.isError && (
        <ErrorState
          error={warehousesQuery.error}
          onRetry={() => void warehousesQuery.refetch()}
        />
      )}
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
              <p className={styles.muted}>{warehouseFilter === '' ? 'Співробітників ще немає — додайте першого.' : 'На цьому складі немає співробітників.'}</p>
            ) : (
              <ul className={styles.rows}>
                {users.map((u) => (
                  <EmployeeRow
                    key={u.user_id}
                    user={u}
                    canManageUsers={canManageUsers}
                    isCurrentUser={u.user_id === session?.user.user_id}
                    onToggleStatus={setPendingUser}
                    onAssignWarehouse={setAssignmentUser}
                    warehouseName={
                      u.warehouse_id === null
                        ? 'Без складу'
                        : warehouses.find(
                          (warehouse) => warehouse.warehouse_id === u.warehouse_id,
                        )?.warehouse_name ?? `Склад №${u.warehouse_id}`
                    }
                  />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
      {assignmentUser && (
        <AssignWarehouseModal
          key={assignmentUser.user_id}
          user={assignmentUser}
          onClose={() => setAssignmentUser(null)}
        />
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
  warehouseName,
  canManageUsers,
  isCurrentUser,
  onToggleStatus,
  onAssignWarehouse,
}: {
  warehouseName: string,
  user: User;
  canManageUsers: boolean;
  isCurrentUser: boolean;
  onToggleStatus: (user: User) => void;
  onAssignWarehouse: (user: User) => void;
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
      <p className={styles.warehouse}>
        <span className={styles.warehouseLabel}>Склад</span>
        {warehouseName}
      </p>
      <UserStatusBadge status={u.status} />
      {canManageUsers && u.role === 'warehouse_manager' && (
        <Button
          variant='secondary'
          onClick={() => onAssignWarehouse(u)}
        >
          Призначити на склад
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
