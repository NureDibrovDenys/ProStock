import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowLeft, Check, Loader, Lock, Pencil, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import { getCounterparties } from '../api/directories';
import {
  ORDER_STATUS_LABELS,
  PACKAGE_LABELS,
  checkInboundCapacity,
  createInboundOrder,
  getInboundOrder,
  inboundNumber,
  postInboundOrder,
  updateInboundOrder,
} from '../api/orders';
import { getProduct } from '../api/products';
import {
  UNIT_LABELS,
  type CapacityCheck,
  type InboundOrder,
  type InboundOrderItemPayload,
  type InboundOrderPayload,
  type OrderStatus,
  type PackageType,
  type Product,
} from '../api/types';
import { Button } from '../components/Button';
import { ProductPicker } from '../components/ProductPicker';
import { ErrorState, LoadingState } from '../components/ui';
import { useCurrentWarehouse } from '../hooks/useCurrentWarehouse';
import { useWarehouseName } from '../hooks/useWarehouse';
import { cx } from '../lib/cx';
import { plural } from '../lib/format';
import styles from './OrderForm.module.css';
import {
  Field,
  QUANTITY_PATTERN,
  fromDateInput,
  parseQuantity,
  quantityToInput,
  toDateInput,
} from './orderFormShared';

type Line = {
  key: number;
  product: Product | null;
  quantity: string;
  packageType: PackageType;
};

type LineErrors = { product?: string; quantity?: string };

type Errors = {
  supplier?: string;
  invoiceNumber?: string;
  date?: string;
  items?: string;
  lines: Record<number, LineErrors>;
};

type Capacity =
  { state: 'idle' } | { state: 'checking' } | { state: 'unavailable' } | { state: 'done'; result: CapacityCheck };

const NO_ERRORS: Errors = { lines: {} };
const PACKAGES: PackageType[] = ['box', 'pallet'];
let nextKey = 1;
const emptyLine = (): Line => ({ key: nextKey++, product: null, quantity: '', packageType: 'box' });

function lineTotals(line: Line): { volume: number; weight: number } | null {
  if (!line.product || !QUANTITY_PATTERN.test(line.quantity.trim())) return null;
  const quantity = parseQuantity(line.quantity);
  if (quantity <= 0) return null;
  const { width, length, height, weight } = line.product;
  return {
    volume: Number(width) * Number(length) * Number(height) * quantity,
    weight: Number(weight) * quantity,
  };
}

const volumeFormat = new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
const weightFormat = new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 2 });
const percentFormat = new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 0 });

function validateLines(lines: Line[]): Pick<Errors, 'items' | 'lines'> {
  const result: Pick<Errors, 'items' | 'lines'> = { lines: {} };
  if (lines.length === 0) result.items = 'Додайте хоча б одну позицію';
  for (const line of lines) {
    const errors: LineErrors = {};
    if (!line.product) errors.product = 'Оберіть товар';
    const raw = line.quantity.trim();
    if (!raw) errors.quantity = 'Вкажіть';
    else if (!QUANTITY_PATTERN.test(raw)) errors.quantity = 'До 2 знаків після коми';
    else if (parseQuantity(raw) <= 0) errors.quantity = 'Має бути > 0';
    if (errors.product || errors.quantity) result.lines[line.key] = errors;
  }

  const seen = new Set<string>();
  for (const line of lines) {
    if (!line.product) continue;
    const id = `${line.product.product_id}:${line.packageType}`;
    if (seen.has(id)) {
      result.lines[line.key] = {
        ...result.lines[line.key],
        product: `Уже є в накладній з пакуванням «${PACKAGE_LABELS[line.packageType]}» - збільште кількість у тому рядку`,
      };
    }
    seen.add(id);
  }
  return result;
}

type HeaderFields = { supplierId: string; invoiceNumber: string; date: string };

function validate(header: HeaderFields, lines: Line[], checkPastDate: boolean): Errors {
  const errors: Errors = { ...validateLines(lines) };
  if (!header.supplierId) errors.supplier = 'Оберіть постачальника з довідника';
  const invoice = header.invoiceNumber.trim();
  if (!invoice) errors.invoiceNumber = 'Вкажіть номер документа постачальника';
  else if (invoice.length > 50) errors.invoiceNumber = 'Не більше 50 символів';
  if (!header.date) errors.date = 'Вкажіть дату поставки';
  else if (checkPastDate && header.date < toDateInput(new Date()))
    errors.date = 'Дата поставки не може бути в минулому';
  return errors;
}

function countErrors(errors: Errors): number {
  const header = [errors.supplier, errors.invoiceNumber, errors.date, errors.items].filter(Boolean).length;
  const lines = Object.values(errors.lines).reduce(
    (sum, line) => sum + (line.product ? 1 : 0) + (line.quantity ? 1 : 0),
    0,
  );
  return header + lines;
}

const toItems = (lines: Line[]): InboundOrderItemPayload[] =>
  lines.map((line) => ({
    product_id: (line.product as Product).product_id,
    quantity: parseQuantity(line.quantity),
    package_type: line.packageType,
  }));

export function InboundOrderFormPage() {
  const { id } = useParams();
  const editId = id ? Number(id) : null;

  const orderQuery = useQuery({
    queryKey: ['inbound-orders', editId],
    queryFn: () => getInboundOrder(editId as number),
    enabled: editId !== null,
  });

  const productIds = [...new Set(orderQuery.data?.items.map((item) => item.product_id) ?? [])];
  const productQueries = useQueries({
    queries: productIds.map((productId) => ({
      queryKey: ['products', 'one', productId],
      queryFn: () => getProduct(productId),
    })),
  });

  if (editId === null) return <InboundOrderForm key="new" order={null} products={[]} />;

  const failed = orderQuery.isError ? orderQuery : productQueries.find((q) => q.isError);
  if (failed) return <ErrorState error={failed.error} onRetry={() => failed.refetch()} />;
  if (!orderQuery.data || productQueries.some((q) => q.isPending)) return <LoadingState />;

  const products = productQueries.map((q) => q.data as Product);
  return <InboundOrderForm key={editId} order={orderQuery.data} products={products} />;
}

function InboundOrderForm({ order, products }: { order: InboundOrder | null; products: Product[] }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const warehouseId = useCurrentWarehouse();
  const warehouseName = useWarehouseName();
  const isEdit = order !== null;
  const status: OrderStatus = order?.order_status ?? 'draft';
  const readOnly = status !== 'draft';

  const initialDate = useRef(order ? toDateInput(new Date(order.expected_delivery_date)) : '');
  const [header, setHeader] = useState<HeaderFields>({
    supplierId: order ? String(order.supplier_id) : '',
    invoiceNumber: order?.invoice_number ?? '',
    date: initialDate.current,
  });
  const [note, setNote] = useState('');
  const [lines, setLines] = useState<Line[]>(() =>
    order
      ? order.items.map((item) => ({
          key: nextKey++,
          product: products.find((p) => p.product_id === item.product_id) ?? null,
          quantity: quantityToInput(item.quantity),
          packageType: item.package_type === 'pallet' ? 'pallet' : 'box',
        }))
      : [emptyLine()],
  );
  const [errors, setErrors] = useState<Errors>(NO_ERRORS);
  const [capacity, setCapacity] = useState<Capacity>({ state: 'idle' });

  const suppliersQuery = useQuery({
    queryKey: ['directories', 'suppliers'],
    queryFn: () => getCounterparties('suppliers'),
  });
  const suppliers = (suppliersQuery.data ?? []).filter(
    (s) => s.status === 'active' || (order !== null && s.id === order.supplier_id),
  );

  const totals = useMemo(() => {
    let volume = 0;
    let weight = 0;
    for (const line of lines) {
      const t = lineTotals(line);
      if (t) {
        volume += t.volume;
        weight += t.weight;
      }
    }
    return { volume, weight };
  }, [lines]);

  const duplicateKeys = useMemo(() => {
    const seen = new Set<string>();
    const duplicates = new Set<number>();
    for (const line of lines) {
      if (!line.product) continue;
      const id = `${line.product.product_id}:${line.packageType}`;
      if (seen.has(id)) duplicates.add(line.key);
      seen.add(id);
    }
    return duplicates;
  }, [lines]);

  const isTakenFor = (line: Line) => (product: Product) =>
    lines.some(
      (other) =>
        other.key !== line.key && other.product?.product_id === product.product_id && other.packageType === line.packageType,
    );

  useEffect(() => {
    setCapacity((prev) => (prev.state === 'idle' ? prev : { state: 'idle' }));
  }, [lines]);

  const saveMutation = useMutation({
    mutationFn: (payload: InboundOrderPayload) =>
      order ? updateInboundOrder(order.inbound_order_id, payload) : createInboundOrder(payload),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ['inbound-orders'] });
      toast.success(`Накладну ${inboundNumber(saved.inbound_order_id)} збережено як чернетку`);
      navigate('/orders');
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return;
      if (error.status === 400 && /invoice number/i.test(error.message)) {
        setErrors((prev) => ({ ...prev, invoiceNumber: 'Накладна з таким номером документа вже існує' }));
      } else if (error.status === 404 && /supplier/i.test(error.message)) {
        setErrors((prev) => ({ ...prev, supplier: 'Постачальника немає в базі - оберіть іншого' }));
      }
    },
  });

  const postMutation = useMutation({
    mutationFn: async () => {
      const checkPastDate = !isEdit || header.date !== initialDate.current;
      const nextErrors = validate(header, lines, checkPastDate);
      setErrors(nextErrors);
      if (countErrors(nextErrors) > 0) {
        throw new Error('VALIDATION');
      }
      const payload: InboundOrderPayload = {
        supplier_id: Number(header.supplierId),
        warehouse_id: warehouseId as number,
        invoice_number: header.invoiceNumber.trim(),
        expected_delivery_date: fromDateInput(header.date),
        items: toItems(lines),
      };
      const target = order ?? (await createInboundOrder(payload));
      return postInboundOrder(target.inbound_order_id);
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['inbound-orders'] });
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
      toast.success(`Накладну ${inboundNumber(result.order_id)} проведено`);
      navigate('/orders');
    },
    onError: (error) => {
      if (error instanceof Error && error.message === 'VALIDATION') return;
    },
  });

  const capacityMutation = useMutation({
    mutationFn: (items: InboundOrderItemPayload[]) =>
      warehouseId !== null
        ? checkInboundCapacity(warehouseId, items)
        : Promise.reject(new Error('Склад не обрано')),
    onMutate: () => setCapacity({ state: 'checking' }),
    onSuccess: (result) => setCapacity({ state: 'done', result }),
    onError: () => setCapacity({ state: 'unavailable' }),
  });

  const setField = (field: keyof HeaderFields, value: string) => {
    setHeader((prev) => ({ ...prev, [field]: value }));
    const errorKey = field === 'date' ? 'date' : field === 'supplierId' ? 'supplier' : 'invoiceNumber';
    if (errors[errorKey]) setErrors((prev) => ({ ...prev, [errorKey]: undefined }));
    saveMutation.reset();
  };

  const updateLine = (key: number, patch: Partial<Line>) => {
    setLines((prev) => prev.map((line) => (line.key === key ? { ...line, ...patch } : line)));
    if (errors.lines[key]) {
      setErrors((prev) => {
        const lineErrors = { ...prev.lines[key] };
        if ('product' in patch || 'packageType' in patch) delete lineErrors.product;
        if ('quantity' in patch) delete lineErrors.quantity;
        return { ...prev, lines: { ...prev.lines, [key]: lineErrors } };
      });
    }
    saveMutation.reset();
  };

  const removeLine = (key: number) => {
    setLines((prev) => prev.filter((line) => line.key !== key));
    setErrors((prev) => {
      const { [key]: _removed, ...rest } = prev.lines;
      return { ...prev, lines: rest };
    });
  };

  const addLine = () => {
    setLines((prev) => [...prev, emptyLine()]);
    setErrors((prev) => ({ ...prev, items: undefined }));
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (saveMutation.isPending || readOnly) return;
    const checkPastDate = !isEdit || header.date !== initialDate.current;
    const nextErrors = validate(header, lines, checkPastDate);
    setErrors(nextErrors);
    if (countErrors(nextErrors) > 0) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    saveMutation.mutate({
      supplier_id: Number(header.supplierId),
      warehouse_id: warehouseId as number,
      invoice_number: header.invoiceNumber.trim(),
      expected_delivery_date: fromDateInput(header.date),
      items: toItems(lines),
    });
  };

  const handleCheckCapacity = () => {
    const lineErrors = validateLines(lines);
    setErrors((prev) => ({ ...prev, ...lineErrors }));
    if (lineErrors.items || Object.keys(lineErrors.lines).length > 0) return;
    capacityMutation.mutate(toItems(lines));
  };

  const errorCount = countErrors(errors);
  const serverError =
    saveMutation.isError && !errors.invoiceNumber && !errors.supplier
      ? saveMutation.error instanceof ApiError
        ? saveMutation.error.message
        : 'Не вдалося зберегти накладну'
      : null;
  const postError = postMutation.isError
    ? postMutation.error instanceof ApiError
      ? postMutation.error
      : new ApiError(500, 'Не вдалося провести накладну')
    : null;
  const doesNotFit = capacity.state === 'done' && !capacity.result.fits;
  const supplierKnown = suppliers.some((s) => String(s.id) === header.supplierId);

  return (
    <form className={styles.page} onSubmit={handleSubmit} noValidate>
      <div>
        <Link to="/orders" className={styles.back}>
          <ArrowLeft size={16} aria-hidden /> Назад до накладних
        </Link>
      </div>

      <div className={styles.titleRow}>
        <h1 className={styles.title}>
          {order ? `Прихідна накладна ${inboundNumber(order.inbound_order_id)}` : 'Нова прихідна накладна'}
        </h1>
        <span className={cx(styles.statusChip, status !== 'draft' && styles.statusChipActive)}>
          {status === 'draft' && <Pencil size={11} aria-hidden />}
          {ORDER_STATUS_LABELS[status]}
        </span>
      </div>

      {errorCount > 0 && (
        <p className={styles.banner} role="alert">
          <AlertTriangle size={16} aria-hidden />
          Накладну не збережено: виправте {errorCount} {plural(errorCount, ['помилку', 'помилки', 'помилок'])} в полях,
          позначених червоним.
        </p>
      )}
      {serverError && (
        <p className={styles.banner} role="alert">
          <AlertTriangle size={16} aria-hidden />
          {serverError}
        </p>
      )}
      {postError && (
        <div className={cx(styles.banner, styles.bannerBad)} role="alert">
          <AlertTriangle size={16} aria-hidden />
          <div>
            <p>{postError.message}</p>
            {postError.shortages.length > 0 && (
              <ul className={styles.shortageList}>
                {postError.shortages.map((shortage: any) => (
                  <li key={shortage.product_id}>
                    {shortage.product_name}: потрібно {shortage.requested}, розміщено {shortage.placed}, не вмістилося{' '}
                    {shortage.unplaced} ({shortage.reason})
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {readOnly && (
        <p className={styles.info}>
          Накладна вже в статусі «{ORDER_STATUS_LABELS[status]}» - редагувати можна лише чернетки.
        </p>
      )}

      <div className={styles.layout}>
        <div className={styles.column}>
          {}
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>Загальна інформація</h2>
            <div className={styles.grid}>
              <Field label="Номер">
                <div className={styles.locked}>
                  {order ? inboundNumber(order.inbound_order_id) : 'Буде присвоєно автоматично'}
                  <Lock size={13} aria-hidden />
                </div>
              </Field>
              <Field label="Склад">
                <div className={styles.locked}>
                  {warehouseName}
                  <Lock size={13} aria-hidden />
                </div>
              </Field>

              <Field label="Постачальник *" htmlFor="supplier" error={errors.supplier} wide>
                <select
                  id="supplier"
                  className={cx(
                    styles.control,
                    styles.select,
                    errors.supplier && styles.invalid,
                    !header.supplierId && styles.placeholder,
                  )}
                  value={header.supplierId}
                  onChange={(event) => setField('supplierId', event.target.value)}
                  disabled={readOnly}
                  aria-invalid={errors.supplier ? true : undefined}
                >
                  <option value="">{suppliersQuery.isPending ? 'Завантаження…' : 'Оберіть постачальника'}</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplier.company_name}
                    </option>
                  ))}
                  {header.supplierId && !supplierKnown && !suppliersQuery.isPending && (
                    <option value={header.supplierId}>Постачальник №{header.supplierId}</option>
                  )}
                </select>
                {!readOnly && (
                  <Link to="/directories/suppliers/new" className={styles.addLink}>
                    + Новий постачальник
                  </Link>
                )}
              </Field>

              <Field label="№ супровідного документа *" htmlFor="invoice" error={errors.invoiceNumber}>
                <input
                  id="invoice"
                  className={cx(styles.control, errors.invoiceNumber && styles.invalid)}
                  placeholder="ВН-1187"
                  autoComplete="off"
                  maxLength={50}
                  value={header.invoiceNumber}
                  onChange={(event) => setField('invoiceNumber', event.target.value)}
                  disabled={readOnly}
                  aria-invalid={errors.invoiceNumber ? true : undefined}
                />
              </Field>
              <Field label="Очікувана дата поставки *" htmlFor="date" error={errors.date}>
                <input
                  id="date"
                  type="date"
                  className={cx(styles.control, errors.date && styles.invalid)}
                  min={isEdit ? undefined : toDateInput(new Date())}
                  value={header.date}
                  onChange={(event) => setField('date', event.target.value)}
                  disabled={readOnly}
                  aria-invalid={errors.date ? true : undefined}
                />
              </Field>

              <Field
                label="Примітка"
                htmlFor="note"
                hint="Поки не зберігається: у бекенді накладної ще немає цього поля"
                wide
              >
                <textarea
                  id="note"
                  className={cx(styles.control, styles.textarea)}
                  placeholder="Розвантаження з 08:00, попередити охорону"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  disabled={readOnly}
                />
              </Field>
            </div>
          </section>

          {}
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>Позиції</h2>
            <div className={styles.lines} role="table" aria-label="Позиції накладної">
              <div className={cx(styles.line, styles.lineHead)} role="row">
                <span role="columnheader">Товар (SKU або назва)</span>
                <span role="columnheader">Кількість</span>
                <span role="columnheader">Од. виміру</span>
                <span role="columnheader">Пакування</span>
                <span role="columnheader">Об'єм, м³</span>
                <span role="columnheader">Вага, кг</span>
                <span />
              </div>

              {lines.map((line, index) => {
                const lineErrors: LineErrors = {
                  ...errors.lines[line.key],
                  product:
                    errors.lines[line.key]?.product ??
                    (duplicateKeys.has(line.key)
                      ? `Уже є в накладній з пакуванням «${PACKAGE_LABELS[line.packageType]}» - збільште кількість у тому рядку`
                      : undefined),
                };
                const t = lineTotals(line);
                return (
                  <div key={line.key} className={styles.line} role="row">
                    <div className={styles.cell} role="cell" data-label="Товар">
                      <ProductPicker
                        value={line.product}
                        onChange={(product) => updateLine(line.key, { product })}
                        invalid={Boolean(lineErrors.product)}
                        disabled={readOnly}
                        isTaken={isTakenFor(line)}
                        takenLabel={`уже в накладній (${PACKAGE_LABELS[line.packageType].toLowerCase()})`}
                        aria-label={`Товар, позиція ${index + 1}`}
                      />
                      {lineErrors.product && <span className={styles.cellError}>{lineErrors.product}</span>}
                    </div>
                    <div className={styles.cell} role="cell" data-label="Кількість">
                      <input
                        className={cx(styles.control, styles.small, lineErrors.quantity && styles.invalid)}
                        inputMode="decimal"
                        placeholder="0"
                        value={line.quantity}
                        onChange={(event) => updateLine(line.key, { quantity: event.target.value })}
                        disabled={readOnly}
                        aria-label={`Кількість, позиція ${index + 1}`}
                        aria-invalid={lineErrors.quantity ? true : undefined}
                      />
                      {lineErrors.quantity && <span className={styles.cellError}>{lineErrors.quantity}</span>}
                    </div>
                    <div className={styles.cell} role="cell" data-label="Од. виміру">
                      <span className={cx(styles.readout, styles.small)} title="Одиниця виміру товару з каталогу">
                        {line.product
                          ? (UNIT_LABELS[line.product.unit_of_measure] ?? line.product.unit_of_measure)
                          : '-'}
                      </span>
                    </div>
                    <div className={styles.cell} role="cell" data-label="Пакування">
                      <div className={styles.segmented} role="group" aria-label={`Пакування, позиція ${index + 1}`}>
                        {PACKAGES.map((pkg) => (
                          <button
                            key={pkg}
                            type="button"
                            className={cx(styles.segment, line.packageType === pkg && styles.segmentActive)}
                            aria-pressed={line.packageType === pkg}
                            onClick={() => updateLine(line.key, { packageType: pkg })}
                            disabled={readOnly}
                          >
                            {PACKAGE_LABELS[pkg]}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className={styles.cell} role="cell" data-label="Об'єм, м³">
                      <span className={cx(styles.readout, styles.small)}>
                        {t ? volumeFormat.format(t.volume) : '-'}
                      </span>
                    </div>
                    <div className={styles.cell} role="cell" data-label="Вага, кг">
                      <span className={cx(styles.readout, styles.small)}>
                        {t ? weightFormat.format(t.weight) : '-'}
                      </span>
                    </div>
                    <div className={styles.cell} role="cell">
                      <button
                        type="button"
                        className={styles.remove}
                        onClick={() => removeLine(line.key)}
                        disabled={readOnly || lines.length === 1}
                        aria-label={`Видалити позицію ${index + 1}`}
                        title={lines.length === 1 ? 'У накладній має бути хоча б одна позиція' : 'Видалити позицію'}
                      >
                        <Trash2 size={16} aria-hidden />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {errors.items && <p className={styles.cellError}>{errors.items}</p>}
            {!readOnly && (
              <div>
                <button type="button" className={styles.addLine} onClick={addLine}>
                  + Додати позицію
                </button>
              </div>
            )}

            <div className={styles.summary}>
              <span>Разом по партії</span>
              <span>
                {volumeFormat.format(totals.volume)} м³ · {weightFormat.format(totals.weight)} кг
              </span>
            </div>
            <p className={styles.footnote}>
              Об'єм і вага позиції рахуються автоматично з габаритів у довіднику товарів.
            </p>
          </section>
        </div>

        {}
        <aside className={cx(styles.card, styles.aside)}>
          <h2 className={styles.cardTitle}>Перевірка вміщуваності</h2>
          <CapacityPanel capacity={capacity} required={totals.volume} />
        </aside>
      </div>

      {}
      <div className={cx(styles.card, styles.actions)}>
        <Button variant="cancel" onClick={() => navigate('/orders')}>
          Скасувати
        </Button>
        <div className={styles.actionsRight}>
          {doesNotFit && (
            <span className={styles.blocked}>
              <Lock size={13} aria-hidden /> Недостатньо місця на складі
            </span>
          )}
          <Button
            variant="secondary"
            onClick={handleCheckCapacity}
            disabled={readOnly || capacity.state === 'checking'}
          >
            Перевірити вміщуваність
          </Button>
          <Button type="submit" variant="secondary" disabled={readOnly || saveMutation.isPending}>
            {saveMutation.isPending ? (
              <>
                <Loader size={17} className="spin" aria-hidden /> Збереження…
              </>
            ) : (
              'Зберегти чернетку'
            )}
          </Button>
          <Button
            variant="save"
            disabled={readOnly || postMutation.isPending || !header.supplierId || lines.some((l) => !l.product)}
            onClick={() => postMutation.mutate()}
            title={readOnly ? 'Накладна вже проведена' : undefined}
          >
            {postMutation.isPending ? (
              <>
                <Loader size={17} className="spin" aria-hidden /> Проведення…
              </>
            ) : (
              'Провести накладну'
            )}
          </Button>
        </div>
      </div>
    </form>
  );
}

function CapacityPanel({ capacity, required }: { capacity: Capacity; required: number }) {
  if (capacity.state === 'checking') {
    return (
      <p className={styles.muted}>
        <Loader size={14} className="spin" aria-hidden /> Перевіряємо…
      </p>
    );
  }
  if (capacity.state === 'unavailable') {
    return (
      <p className={styles.muted}>
        Перевірка поки недоступна: сервер ще не рахує вільний об'єм полиць складу. Партія займе{' '}
        {volumeFormat.format(required)} м³.
      </p>
    );
  }
  if (capacity.state === 'idle') {
    return <p className={styles.muted}>Перевірку ще не виконано. Перевірте вміщуваність перед проведенням.</p>;
  }

  const {
    fits,
    required_m3,
    free_m3,
    total_m3,
    required_weight_kg,
    free_weight_kg,
    shortages,
  } = capacity.result;
  const percent = (value: number) => (total_m3 > 0 ? percentFormat.format((value / total_m3) * 100) : '0');

  if (fits) {
    return (
      <div className={cx(styles.notice, styles.noticeOk)}>
        <Check size={16} aria-hidden />
        <div>
          <p className={styles.noticeTitle}>Вміщується повністю</p>
          <p>Після приймання вільно {percent(free_m3 - required_m3)}% місткості складу.</p>
          <p className={styles.noticeNote}>Зараз вільно {percent(free_m3)}% місткості.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={cx(styles.notice, styles.noticeBad)}>
        <X size={16} aria-hidden />
        <div>
          <p className={styles.noticeTitle}>Не вміщується</p>
          {shortages.length > 0 ? (
            <ul className={styles.shortageList}>
              {shortages.map((shortage, index) => (
                <li key={`${shortage.product_id}-${index}`}>
                  {shortage.product_name}: {shortage.reason}.
                  Не вмістилося: {shortage.unplaced}.
                </li>
              ))}
            </ul>
          ) : (
            <p>Недостатньо місця для розміщення поставки.</p>
          )}
          <p>
            Об'єм: потрібно {volumeFormat.format(required_m3)} м³,
            доступно {volumeFormat.format(free_m3)} м³.
          </p>
          <p>
            Вага: потрібно {weightFormat.format(required_weight_kg)} кг,
            доступно {weightFormat.format(free_weight_kg)} кг.
          </p>
          <p className={styles.noticeNote}>Зараз вільно {percent(free_m3)}% місткості складу.</p>
        </div>
      </div>
      <div className={cx(styles.notice, styles.noticeWarn)}>
        <AlertTriangle size={15} aria-hidden />
        <p>
          Звільніть місце на полицях, збільште доступну
          вантажопідйомність або зменште кількість товару
          перед проведенням накладної.
        </p>
      </div>
    </>
  );
}
