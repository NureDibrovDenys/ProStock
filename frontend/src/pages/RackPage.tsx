import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus, Printer, QrCode, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import type { Shelf, ShelfStatus } from '../api/types';
import { deleteShelf, listShelves } from '../api/warehouse';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { LabelPrinter } from '../components/labels/LabelPrinter';
import { shelfLabel } from '../components/labels/labelData';
import { INACTIVE_REASONS, ShelfFormModal } from '../components/ShelfFormModal';
import { ShelfQrModal } from '../components/ShelfQrModal';
import { NoWarehouseState } from '../components/NoWarehouseState';
import { StatCard, StatGrid } from '../components/StatCard';
import { ErrorState, LoadingState, PageHeader, ProgressBar } from '../components/ui';
import { useCurrentWarehouse } from '../hooks/useCurrentWarehouse';
import { formatNumber, plural } from '../lib/format';
import styles from './RackPage.module.css';

const SHELF_STATUS_LABELS: Record<ShelfStatus, string> = {
  active: '',
  occupied: '',
  inactive: ' · не функціонує',
};

function inactiveReasonLabel(reason: NonNullable<Shelf['inactive_reason']>): string {
  return INACTIVE_REASONS.find((r) => r.value === reason)?.label ?? 'інша причина';
}

type ShelfModalState = { mode: 'create' } | { mode: 'edit'; shelf: Shelf };

export function RackPage() {
  const warehouseId = useCurrentWarehouse();
  const { rackCode = '' } = useParams();
  const { can } = useAuth();
  const canManage = can('shelves_manage');
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['shelves', warehouseId, rackCode],
    enabled: warehouseId !== null,
    queryFn: () => {
      if (warehouseId === null) {
        throw new Error('Склад не призначено');
      }

      return listShelves(warehouseId, rackCode);
    },
  });
  const shelves = query.data ?? [];

  const [modal, setModal] = useState<ShelfModalState | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Shelf | null>(null);
  const [qrShelf, setQrShelf] = useState<Shelf | null>(null);
  const [printingAll, setPrintingAll] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: (shelf: Shelf) => {
      if (warehouseId === null) {
        throw new Error('Склад не призначено');
      }

      return deleteShelf(warehouseId, rackCode, shelf.shelf_id);
    },
    onSuccess: (_data, shelf) => {
      void queryClient.invalidateQueries({ queryKey: ['shelves', warehouseId, rackCode] });
      void queryClient.invalidateQueries({ queryKey: ['racks', warehouseId] });
      void queryClient.invalidateQueries({ queryKey: ['dashboard', warehouseId] });
      toast.success(`Полицю «${shelf.shelf_code}» видалено`);
      setDeleteTarget(null);
    },
  });

  const capacity = shelves.length;
  // Частка зайнятого об'єму, як на бекенді (fill_service) і на мапі складу. Середнє відсотків
  // полиць тут не годиться: мала заповнена полиця й велика порожня дали б 50%.
  const totalVolume = shelves.reduce((sum, shelf) => sum + (shelf.volume_m3 ?? 0), 0);
  const usedVolume = shelves.reduce((sum, shelf) => sum + (shelf.used_volume_m3 ?? 0), 0);
  const fill = totalVolume > 0 ? Math.round((usedVolume / totalVolume) * 100) : 0;
  const occupied = shelves.filter((shelf) => (shelf.items_count ?? 0) > 0).length;
  const free = capacity - occupied;

  if (warehouseId === null) {
    return <NoWarehouseState />;
  }

  return (
    <>
      <div className={styles.back}>
        <Button variant="secondary" to="/warehouse">
          ← Назад до складу
        </Button>
      </div>

      <PageHeader
        title={`Стелаж ${rackCode}`}
        subtitle={`${capacity} ${plural(capacity, ['полиця', 'полиці', 'полиць'])}`}
      />

      {query.isPending && <LoadingState />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.isSuccess && (
        <>
          <StatGrid>
            <StatCard label="Заповненість" value={`${fill}%`} caption="від загального об'єму" />
            <StatCard label="Місткість" value={String(capacity)} caption={plural(capacity, ['полиця', 'полиці', 'полиць'])} />
            <StatCard label="Зайнято" value={String(occupied)} caption={plural(occupied, ['полиця з товаром', 'полиці з товаром', 'полиць з товаром'])} />
            <StatCard label="Вільно" value={String(free)} caption={plural(free, ['порожня полиця', 'порожні полиці', 'порожніх полиць'])} />
          </StatGrid>

          <section className={styles.shelves}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.title}>Полиці</h2>
              <div className={styles.headerActions}>
                {shelves.length > 0 && (
                  <Button variant="secondary" onClick={() => setPrintingAll(true)} disabled={printingAll}>
                    <Printer size={16} aria-hidden /> Друкувати етикетки
                  </Button>
                )}
                {canManage && (
                  <Button variant="secondary" onClick={() => setModal({ mode: 'create' })}>
                    <Plus size={16} aria-hidden /> Додати полицю
                  </Button>
                )}
              </div>
            </div>

            {shelves.length === 0 ? (
              <div className={styles.empty}>
                <p>У стелажа ще немає полиць</p>
                {canManage && (
                  <Button onClick={() => setModal({ mode: 'create' })}>
                    <Plus size={16} aria-hidden /> Створити першу полицю
                  </Button>
                )}
              </div>
            ) : (
              <div className={styles.scroll}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th scope="col">Полиця</th>
                      <th scope="col">Габарити, м (Д×Ш×В)</th>
                      <th scope="col">Навантаження</th>
                      <th scope="col">Зайнято</th>
                      <th scope="col">Заповненість</th>
                      <th scope="col" className={styles.actionsHeader}>
                        Дії
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {shelves.map((shelf) => {
                      const percent = Math.round(shelf.volume_fill_percent ?? 0);
                      return (
                        <tr key={shelf.shelf_id}>
                          <td className={styles.shelfName}>
                            {shelf.shelf_code}
                            {SHELF_STATUS_LABELS[shelf.status]}
                            {shelf.status === 'inactive' && shelf.inactive_reason && (
                              <span className={styles.reason}> · {inactiveReasonLabel(shelf.inactive_reason)}</span>
                            )}
                          </td>
                          <td className={styles.numeric}>
                            {formatNumber(Number(shelf.length))} × {formatNumber(Number(shelf.width))} ×{' '}
                            {formatNumber(Number(shelf.height))}
                          </td>
                          <td className={styles.numeric}>
                            {formatNumber(Number(shelf.max_weight))} {plural(Number(shelf.max_weight), ['кілограм', 'кілограми', 'кілограмів'])}
                          </td>
                          <td>{shelf.is_occupied ? '1 / 1' : '0 / 1'} палет</td>
                          <td>
                            <div className={styles.fill}>
                              <ProgressBar percent={percent} />
                              <span className={styles.percent}>{percent}%</span>
                            </div>
                            <span className={styles.meta}>
                              {formatNumber(Number(shelf.used_volume_m3))} / {formatNumber(Number(shelf.volume_m3))} м³ ·{' '}
                              {formatNumber(Number(shelf.used_weight_kg))} / {formatNumber(Number(shelf.max_weight))} кг
                            </span>
                          </td>
                          <td>
                            <div className={styles.rowActions}>
                              <button
                                type="button"
                                className={styles.iconButton}
                                onClick={() => setQrShelf(shelf)}
                                aria-label={`QR полиці ${shelf.shelf_code}`}
                                title="QR та етикетка"
                              >
                                <QrCode size={16} aria-hidden />
                              </button>
                              {canManage && (
                                <>
                                  <button
                                    type="button"
                                    className={styles.iconButton}
                                    onClick={() => setModal({ mode: 'edit', shelf })}
                                    aria-label={`Редагувати полицю ${shelf.shelf_code}`}
                                    title="Редагувати"
                                  >
                                    <Pencil size={16} aria-hidden />
                                  </button>
                                  <button
                                    type="button"
                                    className={`${styles.iconButton} ${styles.danger}`}
                                    onClick={() => {
                                      deleteMutation.reset();
                                      setDeleteTarget(shelf);
                                    }}
                                    aria-label={`Видалити полицю ${shelf.shelf_code}`}
                                    title="Видалити"
                                  >
                                    <Trash2 size={16} aria-hidden />
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {modal && (
        <ShelfFormModal
          warehouseId={warehouseId}
          rackCode={rackCode}
          shelf={modal.mode === 'edit' ? modal.shelf : undefined}
          onClose={() => setModal(null)}
        />
      )}

      {qrShelf && <ShelfQrModal shelf={qrShelf} rackCode={rackCode} onClose={() => setQrShelf(null)} />}

      {printingAll && (
        <LabelPrinter
          labels={shelves.map((shelf) => shelfLabel(shelf, rackCode))}
          layout="sheet"
          onDone={() => setPrintingAll(false)}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Видалити полицю?"
          message={`Полицю «${deleteTarget.shelf_code}» буде видалено зі стелажа «${rackCode}».`}
          details="Дію не можна скасувати."
          busy={deleteMutation.isPending}
          error={
            deleteMutation.isError
              ? deleteMutation.error instanceof ApiError
                ? deleteMutation.error.message
                : 'Не вдалося видалити полицю'
              : null
          }
          onConfirm={() => deleteMutation.mutate(deleteTarget)}
          onClose={() => {
            if (!deleteMutation.isPending) setDeleteTarget(null);
          }}
        />
      )}
    </>
  );
}
