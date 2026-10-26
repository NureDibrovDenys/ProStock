import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  Loader,
  Package,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  Upload,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '../api/client';
import { deleteProduct, exportProducts, getCategories, getProducts } from '../api/products';
import type { ImportReport, Product, ProductSortField, UnitOfMeasure } from '../api/types';
import { UNIT_LABELS } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ImportProductsModal } from '../components/ImportProductsModal';
import { ProductFormModal } from '../components/ProductFormModal';
import { Card, ErrorState, LoadingState, PageHeader } from '../components/ui';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import styles from './ProductsPage.module.css';

const PAGE_SIZE = 20;

type SortState = { by: ProductSortField; order: 'asc' | 'desc' };

const numberFormat = new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 3 });

function formatNumber(value: string | null): string {
  if (value === null || value === '') return '—';
  const parsed = Number(value);
  return Number.isFinite(parsed) ? numberFormat.format(parsed) : value;
}

function formatDimensions(product: Product): string {
  return `${formatNumber(product.length)} × ${formatNumber(product.width)} × ${formatNumber(product.height)}`;
}

function pluralPositions(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'позиція';
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return 'позиції';
  return 'позицій';
}

function buildPages(current: number, total: number): number[] {
  const pages: number[] = [];
  const start = Math.max(1, Math.min(current - 2, total - 4));
  for (let page = start; page <= Math.min(total, start + 4); page += 1) pages.push(page);
  return pages;
}

export function ProductsPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 350);
  const [categoryId, setCategoryId] = useState<string>('');
  const [unit, setUnit] = useState<UnitOfMeasure | ''>('');
  const [sort, setSort] = useState<SortState>({ by: 'product_id', order: 'asc' });
  const [page, setPage] = useState(1);

  const [formTarget, setFormTarget] = useState<{ open: boolean; product: Product | null }>({
    open: false,
    product: null,
  });
  const [importOpen, setImportOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [exporting, setExporting] = useState<'csv' | 'xlsx' | null>(null);

  const filters = {
    search: debouncedSearch.trim() || undefined,
    category_id: categoryId ? Number(categoryId) : undefined,
    unit_of_measure: unit || undefined,
    sort_by: sort.by,
    sort_order: sort.order,
  };

  const productsQuery = useQuery({
    queryKey: ['products', filters, page],
    queryFn: () => getProducts({ ...filters, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  const categoriesQuery = useQuery({ queryKey: ['categories'], queryFn: getCategories });

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, categoryId, unit]);

  const deleteMutation = useMutation({
    mutationFn: (product: Product) => deleteProduct(product.product_id),
    onSuccess: (_, product) => {
      void queryClient.invalidateQueries({ queryKey: ['products'] });
      void queryClient.invalidateQueries({ queryKey: ['categories'] });
      setDeleteTarget(null);
      setBanner({ type: 'success', text: `Товар «${product.name}» видалено` });
    },
  });

  const categories = categoriesQuery.data ?? [];
  const data = productsQuery.data;
  const products = data?.items ?? [];
  const hasFilters = Boolean(debouncedSearch || categoryId || unit);

  const resetFilters = () => {
    setSearch('');
    setCategoryId('');
    setUnit('');
    setSort({ by: 'product_id', order: 'asc' });
    setPage(1);
  };

  const toggleSort = (field: ProductSortField) => {
    setSort((prev) =>
      prev.by === field ? { by: field, order: prev.order === 'asc' ? 'desc' : 'asc' } : { by: field, order: 'asc' },
    );
    setPage(1);
  };

  const sortIcon = (field: ProductSortField) => {
    if (sort.by !== field) return <ArrowUpDown size={14} aria-hidden />;
    return sort.order === 'asc' ? <ArrowUp size={14} aria-hidden /> : <ArrowDown size={14} aria-hidden />;
  };

  const ariaSort = (field: ProductSortField): 'ascending' | 'descending' | 'none' => {
    if (sort.by !== field) return 'none';
    return sort.order === 'asc' ? 'ascending' : 'descending';
  };

  const handleExport = async (format: 'csv' | 'xlsx') => {
    setExporting(format);
    setBanner(null);
    try {
      await exportProducts(format, filters);
      setBanner({
        type: 'success',
        text: `Файл ${format.toUpperCase()} із ${data?.total ?? 0} товарами завантажено`,
      });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Не вдалося експортувати каталог';
      setBanner({ type: 'error', text: message });
    } finally {
      setExporting(null);
    }
  };

  const handleImported = (report: ImportReport) => {
    void queryClient.invalidateQueries({ queryKey: ['products'] });
    void queryClient.invalidateQueries({ queryKey: ['categories'] });
    const parts = [
      `створено ${report.created}`,
      `оновлено ${report.updated}`,
      report.failed ? `помилок ${report.failed}` : 'без помилок',
    ];
    setBanner({
      type: report.failed ? 'error' : 'success',
      text: `Імпорт «${report.filename}»: ${parts.join(', ')}`,
    });
  };

  const canWrite = can('products_write');
  const canDelete = can('products_delete');
  const canImport = can('products_import');

  const subtitle = useMemo(() => {
    if (!data) return undefined;
    const total = `${data.total} ${pluralPositions(data.total)}`;
    return canWrite ? `${total} у каталозі` : `${total} у каталозі · режим перегляду`;
  }, [data, canWrite]);

  return (
    <>
      <PageHeader
        title="Товари"
        subtitle={subtitle}
        actions={
          <>
            {canImport && (
              <button
                type="button"
                className={styles.toolbarButton}
                onClick={() => setImportOpen(true)}
              >
                <Upload size={16} aria-hidden /> Імпорт
              </button>
            )}
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={() => void handleExport('csv')}
              disabled={exporting !== null}
            >
              {exporting === 'csv' ? <Loader size={16} className="spin" aria-hidden /> : <Download size={16} aria-hidden />}
              CSV
            </button>
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={() => void handleExport('xlsx')}
              disabled={exporting !== null}
            >
              {exporting === 'xlsx' ? (
                <Loader size={16} className="spin" aria-hidden />
              ) : (
                <FileSpreadsheet size={16} aria-hidden />
              )}
              Excel
            </button>
            {canWrite && (
              <Button onClick={() => setFormTarget({ open: true, product: null })}>
                <Plus size={18} aria-hidden /> Новий товар
              </Button>
            )}
          </>
        }
      />

      {banner && (
        <div className={`${styles.banner} ${banner.type === 'error' ? styles.bannerError : styles.bannerSuccess}`} role="status">
          {banner.text}
          <button type="button" className={styles.bannerClose} onClick={() => setBanner(null)} aria-label="Закрити повідомлення">
            ×
          </button>
        </div>
      )}

      <Card>
        <div className={styles.filters}>
          <div className={styles.search}>
            <Search size={16} className={styles.searchIcon} aria-hidden />
            <input
              type="search"
              className={styles.searchInput}
              placeholder="Пошук за артикулом або назвою…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Пошук товарів"
            />
          </div>

          <select
            className={styles.filterSelect}
            value={categoryId}
            onChange={(event) => setCategoryId(event.target.value)}
            aria-label="Фільтр за категорією"
          >
            <option value="">Усі категорії</option>
            {categories.map((category) => (
              <option key={category.category_id} value={category.category_id}>
                {category.name} ({category.products_count})
              </option>
            ))}
          </select>

          <select
            className={styles.filterSelect}
            value={unit}
            onChange={(event) => setUnit(event.target.value as UnitOfMeasure | '')}
            aria-label="Фільтр за одиницею виміру"
          >
            <option value="">Усі одиниці</option>
            {(Object.keys(UNIT_LABELS) as UnitOfMeasure[]).map((value) => (
              <option key={value} value={value}>
                {UNIT_LABELS[value]}
              </option>
            ))}
          </select>

          {hasFilters && (
            <button type="button" className={styles.reset} onClick={resetFilters}>
              <RotateCcw size={14} aria-hidden /> Скинути
            </button>
          )}

          <span className={styles.foundCount}>
            {data ? `Знайдено: ${data.total}` : ''}
          </span>
        </div>

        {productsQuery.isPending && <LoadingState label="Завантаження каталогу…" />}
        {productsQuery.isError && (
          <ErrorState error={productsQuery.error} onRetry={() => productsQuery.refetch()} />
        )}

        {data && products.length === 0 && (
          <div className={styles.empty}>
            <Package size={44} aria-hidden />
            <p className={styles.emptyTitle}>{hasFilters ? 'Нічого не знайдено' : 'Каталог порожній'}</p>
            <p className={styles.emptyText}>
              {hasFilters
                ? 'Спробуйте змінити пошуковий запит або скинути фільтри.'
                : 'Додайте перший товар вручну або імпортуйте файл CSV/Excel.'}
            </p>
            {hasFilters ? (
              <Button variant="secondary" onClick={resetFilters}>
                Скинути фільтри
              </Button>
            ) : (
              canWrite && (
                <div className={styles.emptyActions}>
                  <Button onClick={() => setFormTarget({ open: true, product: null })}>
                    <Plus size={18} aria-hidden /> Додати товар
                  </Button>
                  {canImport && (
                    <Button variant="secondary" onClick={() => setImportOpen(true)}>
                      <Upload size={18} aria-hidden /> Імпортувати
                    </Button>
                  )}
                </div>
              )
            )}
          </div>
        )}

        {products.length > 0 && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col" aria-sort={ariaSort('sku_code')}>
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort('sku_code')}>
                      Артикул {sortIcon('sku_code')}
                    </button>
                  </th>
                  <th scope="col" aria-sort={ariaSort('name')}>
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort('name')}>
                      Назва {sortIcon('name')}
                    </button>
                  </th>
                  <th scope="col">Категорія</th>
                  <th scope="col">Од. виміру</th>
                  <th scope="col">Габарити, м (Д×Ш×В)</th>
                  <th scope="col" aria-sort={ariaSort('weight')}>
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort('weight')}>
                      Вага, кг {sortIcon('weight')}
                    </button>
                  </th>
                  <th scope="col" aria-sort={ariaSort('min_stock_level')}>
                    <button
                      type="button"
                      className={styles.sortButton}
                      onClick={() => toggleSort('min_stock_level')}
                    >
                      Мін. залишок {sortIcon('min_stock_level')}
                    </button>
                  </th>
                  {(canWrite || canDelete) && <th scope="col" className={styles.actionsHeader}>Дії</th>}
                </tr>
              </thead>
              <tbody>
                {products.map((product) => (
                  <tr key={product.product_id}>
                    <td>
                      <span className={styles.sku}>{product.sku_code}</span>
                    </td>
                    <td className={styles.name}>{product.name}</td>
                    <td>
                      <span className={styles.category}>{product.category_name ?? '—'}</span>
                    </td>
                    <td>{UNIT_LABELS[product.unit_of_measure] ?? product.unit_of_measure}</td>
                    <td className={styles.numeric}>{formatDimensions(product)}</td>
                    <td className={styles.numeric}>{formatNumber(product.weight)}</td>
                    <td className={styles.numeric}>
                      {product.min_stock_level === null ? (
                        <span className={styles.muted}>—</span>
                      ) : (
                        <span className={styles.minStock}>{formatNumber(product.min_stock_level)}</span>
                      )}
                    </td>
                    {(canWrite || canDelete) && (
                      <td>
                        <div className={styles.rowActions}>
                          {canWrite && (
                            <button
                              type="button"
                              className={styles.iconButton}
                              onClick={() => setFormTarget({ open: true, product })}
                              aria-label={`Редагувати ${product.name}`}
                              title="Редагувати"
                            >
                              <Pencil size={16} aria-hidden />
                            </button>
                          )}
                          {canDelete && (
                            <button
                              type="button"
                              className={`${styles.iconButton} ${styles.danger}`}
                              onClick={() => {
                                deleteMutation.reset();
                                setDeleteTarget(product);
                              }}
                              aria-label={`Видалити ${product.name}`}
                              title="Видалити"
                            >
                              <Trash2 size={16} aria-hidden />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total > 0 && (
          <div className={styles.pagination}>
            <span className={styles.pageInfo}>
              {(data.page - 1) * data.page_size + 1}–{Math.min(data.page * data.page_size, data.total)} з {data.total}
            </span>
            <div className={styles.pageButtons}>
              <button
                type="button"
                className={styles.pageButton}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                disabled={data.page <= 1}
                aria-label="Попередня сторінка"
              >
                <ChevronLeft size={16} aria-hidden />
              </button>
              {buildPages(data.page, data.pages).map((pageNumber) => (
                <button
                  key={pageNumber}
                  type="button"
                  className={`${styles.pageButton} ${pageNumber === data.page ? styles.pageActive : ''}`}
                  onClick={() => setPage(pageNumber)}
                  aria-current={pageNumber === data.page ? 'page' : undefined}
                >
                  {pageNumber}
                </button>
              ))}
              <button
                type="button"
                className={styles.pageButton}
                onClick={() => setPage((value) => Math.min(data.pages, value + 1))}
                disabled={data.page >= data.pages}
                aria-label="Наступна сторінка"
              >
                <ChevronRight size={16} aria-hidden />
              </button>
            </div>
          </div>
        )}
      </Card>

      {formTarget.open && (
        <ProductFormModal
          product={formTarget.product}
          categories={categories}
          onClose={() => setFormTarget({ open: false, product: null })}
          onSaved={(saved) => {
            void queryClient.invalidateQueries({ queryKey: ['products'] });
            void queryClient.invalidateQueries({ queryKey: ['categories'] });
            setFormTarget({ open: false, product: null });
            setBanner({
              type: 'success',
              text: formTarget.product
                ? `Товар «${saved.name}» оновлено`
                : `Товар «${saved.name}» додано до каталогу`,
            });
          }}
          onCategoryCreated={(category) => {
            queryClient.setQueryData(['categories'], (previous: typeof categories | undefined) => {
              if (!previous) return [category];
              return [...previous, category].sort((a, b) => a.name.localeCompare(b.name, 'uk'));
            });
          }}
        />
      )}

      {importOpen && (
        <ImportProductsModal
          onClose={() => setImportOpen(false)}
          onImported={handleImported}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Видалити товар?"
          message={`Товар «${deleteTarget.name}» (${deleteTarget.sku_code}) буде видалено з каталогу.`}
          details="Дію не можна скасувати."
          busy={deleteMutation.isPending}
          error={
            deleteMutation.isError
              ? deleteMutation.error instanceof ApiError
                ? deleteMutation.error.message
                : 'Не вдалося видалити товар'
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
