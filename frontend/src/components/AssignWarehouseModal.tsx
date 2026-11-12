import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import type { User } from '../api/types';
import { assignUserWarehouse } from '../api/users';
import { getWarehouses } from '../api/warehouse';
import { Button } from './Button';
import { Modal } from './Modal';
import { Select } from './Select';
import { ErrorState, LoadingState } from './ui';

type Props = {
  user: User;
  onClose: () => void;
};

export function AssignWarehouseModal({ user, onClose }: Props) {
  const queryClient = useQueryClient();

  const [warehouseId, setWarehouseId] = useState(
    user.warehouse_id === null ? '' : String(user.warehouse_id),
  );

  const warehousesQuery = useQuery({
    queryKey: ['warehouses'],
    queryFn: getWarehouses,
  });

  const assignmentMutation = useMutation({
    mutationFn: (selectedId: number | null) =>
      assignUserWarehouse(user.user_id, selectedId),

    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['users'] });
      onClose();
    },
  });

  const selectedId = warehouseId === '' ? null : Number(warehouseId);
  const hasChanges = selectedId !== user.warehouse_id;

  const selectionExists =
    selectedId === null ||
    warehousesQuery.data?.some(
      (warehouse) => warehouse.warehouse_id === selectedId,
    ) === true;

  function handleClose() {
    if (!assignmentMutation.isPending) {
      onClose();
    }
  }

  return (
    <Modal
      title="Призначення на склад"
      subtitle={`${user.first_name} ${user.last_name}`}
      size="sm"
      onClose={handleClose}
      dismissible={!assignmentMutation.isPending}
      footer={
        <>
          <Button
            variant="secondary"
            onClick={handleClose}
            disabled={assignmentMutation.isPending}
          >
            Скасувати
          </Button>

          <Button
            onClick={() => assignmentMutation.mutate(selectedId)}
            disabled={
              !warehousesQuery.isSuccess ||
              !hasChanges ||
              !selectionExists ||
              assignmentMutation.isPending
            }
          >
            {assignmentMutation.isPending ? 'Збереження…' : 'Зберегти'}
          </Button>
        </>
      }
    >
      {warehousesQuery.isPending && <LoadingState />}

      {warehousesQuery.isError && (
        <ErrorState
          error={warehousesQuery.error}
          onRetry={() => void warehousesQuery.refetch()}
        />
      )}

      {warehousesQuery.isSuccess && (
        <>
          <Select
            label="Склад"
            value={warehouseId}
            disabled={assignmentMutation.isPending}
            onChange={(event) => {
              setWarehouseId(event.target.value);
              assignmentMutation.reset();
            }}
          >
            <option value="">Без складу</option>

            {!selectionExists && (
              <option value={warehouseId} disabled>
                Поточний склад недоступний
              </option>
            )}

            {warehousesQuery.data.map((warehouse) => (
              <option
                key={warehouse.warehouse_id}
                value={String(warehouse.warehouse_id)}
              >
                {warehouse.warehouse_name}
              </option>
            ))}
          </Select>

          {warehousesQuery.data.length === 0 && (
            <p>Складів ще немає. Можна лише зняти поточне призначення.</p>
          )}
        </>
      )}

      {assignmentMutation.isError && (
        <p role="alert">
          {assignmentMutation.error instanceof ApiError
            ? assignmentMutation.error.message
            : 'Не вдалося змінити призначення складу.'}
        </p>
      )}
    </Modal>
  );
}