import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Navigate, NavLink, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import { DIRECTORY_LABELS, deleteCounterparty, getCounterparties, isCounterpartyKind } from '../api/directories';
import type { Counterparty, CounterpartyKind } from '../api/types';
import { Button } from '../components/Button';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ErrorState, LoadingState, PageHeader } from '../components/ui';
import { cx } from '../lib/cx';
import styles from './DirectoriesPage.module.css';

const KINDS: CounterpartyKind[] = ['suppliers', 'recipients'];

/** Організаційно-правові форми не несуть змісту для ініціалів: «ТОВ «Агро-Трейд»» → «АТ». */
const LEGAL_FORMS = /^(ТОВ|ПрАТ|ПАТ|АТ|ФОП|ПП|ДП|КП)\s+/i;

export function counterpartyInitials(name: string): string {
  const words = name
    .replace(LEGAL_FORMS, '')
    .replace(/[«»"'„“”№]/g, ' ')
    // «БудЛайн» → «Буд Лайн»
    .replace(/([a-zа-яїієґ])([A-ZА-ЯЇІЄҐ])/g, '$1 $2')
    .split(/[\s\-.,]+/)
    .filter((word) => /\p{L}/u.test(word));
  const letters = words.length >= 2 ? words[0][0] + words[1][0] : (words[0] ?? '?').slice(0, 2);
  return letters.toUpperCase();
}

/** Supplier and recipient directories (administrator and manager) */
export function DirectoriesPage() {
  const { kind } = useParams();
  if (!isCounterpartyKind(kind)) return <Navigate to="/directories/suppliers" replace />;
  return <DirectoryList key={kind} kind={kind} />;
}

function DirectoryList({ kind }: { kind: CounterpartyKind }) {
  const labels = DIRECTORY_LABELS[kind];
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<Counterparty | null>(null);

  const query = useQuery({ queryKey: ['directories', kind], queryFn: () => getCounterparties(kind) });
  const items = query.data ?? [];

  const deleteMutation = useMutation({
    mutationFn: (item: Counterparty) => deleteCounterparty(kind, item.id),
    onSuccess: (_, item) => {
      void queryClient.invalidateQueries({ queryKey: ['directories', kind] });
      toast.success(`${labels.one} ${item.company_name} видалено`);
      setDeleteTarget(null);
    },
  });

  return (
    <>
      <PageHeader
        title={labels.title}
        subtitle={query.data ? `Усього ${items.length}` : undefined}
        actions={<Button to={`/directories/${kind}/new`}>+ Додати {labels.accusative}</Button>}
      />

      <nav className={styles.switcher} aria-label="Довідники">
        {KINDS.map((k) => (
          <NavLink key={k} to={`/directories/${k}`} className={({ isActive }) => cx(styles.pill, isActive && styles.pillActive)}>
            {DIRECTORY_LABELS[k].title}
          </NavLink>
        ))}
      </nav>

      {query.isPending && <LoadingState />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.data && (
        <section className={styles.list}>
          <h2 className={styles.listTitle}>{labels.listTitle}</h2>
          {items.length === 0 ? (
            <p className={styles.muted}>Довідник порожній — додайте першого {labels.accusative}.</p>
          ) : (
            <ul className={styles.rows}>
              {items.map((item) => (
                <li key={item.id} className={styles.row}>
                  <span className={styles.avatar} aria-hidden>
                    {counterpartyInitials(item.company_name)}
                  </span>
                  <div className={styles.main}>
                    <p className={styles.name}>{item.company_name}</p>
                    <p className={styles.meta}>
                      {[item.contact_person, item.phone_number].filter(Boolean).join(' · ') || 'Контакти не вказані'}
                    </p>
                  </div>
                  <p className={styles.address}>{item.address ?? '—'}</p>
                  <div className={styles.actions}>
                    <button
                      type="button"
                      className={cx(styles.iconButton, styles.edit)}
                      onClick={() => navigate(`/directories/${kind}/${item.id}/edit`)}
                      aria-label={`Редагувати ${item.company_name}`}
                      title="Редагувати"
                    >
                      <Pencil size={18} aria-hidden />
                    </button>
                    <button
                      type="button"
                      className={cx(styles.iconButton, styles.remove)}
                      onClick={() => {
                        deleteMutation.reset();
                        setDeleteTarget(item);
                      }}
                      aria-label={`Видалити ${item.company_name}`}
                      title="Видалити"
                    >
                      <Trash2 size={18} aria-hidden />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title={`Видалити ${labels.accusative}?`}
          message={deleteTarget.company_name}
          details={`${labels.one} зникне з довідника, і його не можна буде обрати в нових накладних.`}
          busy={deleteMutation.isPending}
          error={
            deleteMutation.error instanceof ApiError
              ? deleteMutation.error.message
              : deleteMutation.isError
                ? `Не вдалося видалити ${labels.accusative}`
                : null
          }
          onClose={() => {
            if (!deleteMutation.isPending) setDeleteTarget(null);
          }}
          onConfirm={() => deleteMutation.mutate(deleteTarget)}
        />
      )}
    </>
  );
}
