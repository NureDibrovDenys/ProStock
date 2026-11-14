import { keepPreviousData, useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowLeft, Check, Loader, Lock, Pencil, Trash2 } from 'lucide-react';
import { useMemo, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { ApiError } from '../api/client';
import { getCounterparties } from '../api/directories';
import {
  ORDER_STATUS_LABELS,
  PACKAGE_LABELS,
  createOutboundOrder,
  getAvailableStock,
  getOutboundOrder,
  outboundNumber,
  postOutboundOrder,
  updateOutboundOrder,
} from '../api/orders';
import { getProduct } from '../api/products';
import {
  UNIT_LABELS,
  type OrderStatus,
  type OutboundOrder,
  type OutboundOrderItemPayload,
  type OutboundOrderPayload,
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
  validQuantity,
} from './orderFormShared';

type Line = {
  key: number;
  product: Product | null;
  quantity: string;
  packageType: PackageType;
};

type LineErrors = { product?: string; quantity?: string };

type Errors = {
  recipient?: string;
  date?: string;
  items?: string;
  lines: Record<number, LineErrors>;
};

type HeaderFields = { recipientId: string; date: string };

const NO_ERRORS: Errors = { lines: {} };
const PACKAGES: PackageType[] = ['box', 'pallet'];
const DUPLICATE = (pkg: PackageType) =>
  `Уже є в накладній з пакуванням «${PACKAGE_LABELS[pkg]}» — збільште кількість у тому рядку`;

let nextKey = 1;
const emptyLine = (): Line => ({ key: nextKey++, product: null, quantity: '', packageType: 'box' });

const amountFormat = new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 2 });
const unitLabel = (product: Product) => UNIT_LABELS[product.unit_of_measure] ?? product.unit_of_measure;

function findDuplicates(lines: Line[]): Set<number> {
  const seen = new Set<string>();
  const duplicates = new Set<number>();
  for (const line of lines) {
    if (!line.product) continue;
    const id = `${line.product.product_id}:${line.packageType}`;
    if (seen.has(id)) duplicates.add(line.key);
    seen.add(id);
  }
  return duplicates;
}

function validate(header: HeaderFields, lines: Line[], checkPastDate: boolean): Errors {
  const errors: Errors = { lines: {} };
  if (!header.recipientId) errors.recipient = 'Оберіть одержувача з довідника';
  if (!header.date) errors.date = 'Вкажіть дату відвантаження';
  else if (checkPastDate && header.date < toDateInput(new Date()))
    errors.date = 'Дата відвантаження не може бути в минулому';

  if (lines.length === 0) errors.items = 'Додайте хоча б одну позицію';
  const duplicates = findDuplicates(lines);
  for (const line of lines) {
    const lineErrors: LineErrors = {};
    if (!line.product) lineErrors.product = 'Оберіть товар';
    else if (duplicates.has(line.key)) lineErrors.product = DUPLICATE(line.packageType);
    const raw = line.quantity.trim();
    if (!raw) lineErrors.quantity = 'Вкажіть';
    else if (!QUANTITY_PATTERN.test(raw)) lineErrors.quantity = 'До 2 знаків після коми';
    else if (parseQuantity(raw) <= 0) lineErrors.quantity = 'Має бути > 0';
    if (lineErrors.product || lineErrors.quantity) errors.lines[line.key] = lineErrors;
  }
  return errors;
}

function countErrors(errors: Errors): number {
  const header = [errors.recipient, errors.date, errors.items].filter(Boolean).length;
  const lines = Object.values(errors.lines).reduce(
    (sum, line) => sum + (line.product ? 1 : 0) + (line.quantity ? 1 : 0),
    0,
  );
  return header + lines;
}

const toItems = (lines: Line[]): OutboundOrderItemPayload[] =>
  lines.map((line) => ({
    product_id: (line.product as Product).product_id,
    quantity: parseQuantity(line.quantity),
    package_type: line.packageType,
  }));

export function OutboundOrderFormPage() {
  const { id } = useParams();
  const editId = id ? Number(id) : null;

  const orderQuery = useQuery({
    queryKey: ['outbound-orders', editId],
    queryFn: () => getOutboundOrder(editId as number),
    enabled: editId !== null,
  });

  const productIds = [...new Set(orderQuery.data?.items.map((item) => item.product_id) ?? [])];
  const productQueries = useQueries({
    queries: productIds.map((productId) => ({
      queryKey: ['products', 'one', productId],
      queryFn: () => getProduct(productId),
    })),
  });

  if (editId === null) return <OutboundOrderForm key="new" order={null} products={[]} />;

  const failed = orderQuery.isError ? orderQuery : productQueries.find((q) => q.isError);
  if (failed) return <ErrorState error={failed.error} onRetry={() => failed.refetch()} />;
  if (!orderQuery.data || productQueries.some((q) => q.isPending)) return <LoadingState />;

  const products = productQueries.map((q) => q.data as Product);
  return <OutboundOrderForm key={editId} order={orderQuery.data} products={products} />;
}

function OutboundOrderForm({ order, products }: { order: OutboundOrder | null; products: Product[] }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const warehouseId = useCurrentWarehouse();
  const warehouseName = useWarehouseName();
  const isEdit = order !== null;
  const status: OrderStatus = order?.order_status ?? 'draft';
  const readOnly = status !== 'draft';

  const initialDate = useRef(order ? toDateInput(new Date(order.planned_shipment_date)) : '');
  const [header, setHeader] = useState<HeaderFields>({
    recipientId: order ? String(order.recipient_id) : '',
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

  const recipientsQuery = useQuery({
    queryKey: ['directories', 'recipients'],
    queryFn: () => getCounterparties('recipients'),
  });
  const recipients = (recipientsQuery.data ?? []).filter(
    (r) => r.status === 'active' || (order !== null && r.id === order.recipient_id),
  );

  const stockIds = useMemo(
    () => [...new Set(lines.flatMap((line) => (line.product ? [line.product.product_id] : [])))].sort((a, b) => a - b),
    [lines],
  );
  const stockQuery = useQuery({
    queryKey: ['stock', stockIds, warehouseId],
    queryFn: () => getAvailableStock(stockIds, warehouseId),
    enabled: stockIds.length > 0 && !readOnly,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
  const stock = stockQuery.data;

  
  const requested = useMemo(() => {
    const result = new Map<number, number>();
    for (const line of lines) {
      const quantity = validQuantity(line.quantity);
      if (line.product && quantity !== null) {
        result.set(line.product.product_id, (result.get(line.product.product_id) ?? 0) + quantity);
      }
    }
    return result;
  }, [lines]);

  const availableFor = (line: Line): number | null =>
    line.product && stock ? (stock.get(line.product.product_id) ?? null) : null;

  const isShort = (line: Line) => {
    const available = availableFor(line);
    if (!line.product || available === null || validQuantity(line.quantity) === null) return false;
    return (requested.get(line.product.product_id) ?? 0) > available;
  };

  const duplicateKeys = useMemo(() => findDuplicates(lines), [lines]);

  const isTakenFor = (line: Line) => (product: Product) =>
    lines.some(
      (other) =>
        other.key !== line.key && other.product?.product_id === product.product_id && other.packageType === line.packageType,
    );

  const summary = useMemo(() => {
    let units = 0;
    let positions = 0;
    for (const line of lines) {
      if (!line.product) continue;
      positions += 1;
      units += validQuantity(line.quantity) ?? 0;
    }
    return { positions, units };
  }, [lines]);

  const saveMutation = useMutation({
    mutationFn: (payload: OutboundOrderPayload) =>
      order ? updateOutboundOrder(order.outbound_order_id, payload) : createOutboundOrder(payload),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ['outbound-orders'] });
      toast.success(`Накладну ${outboundNumber(saved.outbound_order_id)} збережено як чернетку`);
      navigate('/orders');
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 404 && /recipient/i.test(error.message)) {
        setErrors((prev) => ({ ...prev, recipient: 'Одержувача немає в базі — оберіть іншого' }));
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
      const payload: OutboundOrderPayload = {
        recipient_id: Number(header.recipientId),
        warehouse_id: warehouseId as number,
        planned_shipment_date: fromDateInput(header.date),
        items: toItems(lines),
      };
      const target = order ?? (await createOutboundOrder(payload));
      return postOutboundOrder(target.outbound_order_id);
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['outbound-orders'] });
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
      void queryClient.invalidateQueries({ queryKey: ['stock'] });
      toast.success(`Накладну ${outboundNumber(result.order_id)} проведено`);
      navigate('/orders');
    },
    onError: (error) => {
      if (error instanceof Error && error.message === 'VALIDATION') return;
    },
  });

  const setField = (field: keyof HeaderFields, value: string) => {
    setHeader((prev) => ({ ...prev, [field]: value }));
    const errorKey = field === 'date' ? 'date' : 'recipient';
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
      recipient_id: Number(header.recipientId),
      warehouse_id: warehouseId as number,
      planned_shipment_date: fromDateInput(header.date),
      items: toItems(lines),
    });
  };

  const errorCount = countErrors(errors);
  const serverError =
    saveMutation.isError && !errors.recipient
      ? saveMutation.error instanceof ApiError
        ? saveMutation.error.message
        : 'Не вдалося зберегти накладну'
      : null;
  const postError = postMutation.isError
    ? postMutation.error instanceof ApiError
      ? postMutation.error
      : new ApiError(500, 'Не вдалося провести накладну')
    : null;
  const shortCount = lines.filter(isShort).length;
  const recipientKnown = recipients.some((r) => String(r.id) === header.recipientId);

  return (
    <form className={styles.page} onSubmit={handleSubmit} noValidate>
      <div>
        <Link to="/orders" className={styles.back}>
          <ArrowLeft size={16} aria-hidden /> Назад до накладних
        </Link>
      </div>

      <div className={styles.titleRow}>
        <h1 className={styles.title}>
          {order ? `Вихідна накладна ${outboundNumber(order.outbound_order_id)}` : 'Нова вихідна накладна'}
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
        <div className={styles.banner} role="alert">
          <AlertTriangle size={16} aria-hidden />
          <div>
            <p>{postError.message}</p>
            {postError.shortages.length > 0 && (
              <ul className={styles.shortageList}>
                {postError.shortages.map((shortage: any) => (
                  <li key={shortage.product_id}>
                    {shortage.product_name}: потрібно {shortage.requested}, доступно {shortage.available}, бракує{' '}
                    {shortage.shortage}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
      {readOnly && (
        <p className={styles.info}>
          Накладна вже в статусі «{ORDER_STATUS_LABELS[status]}» — редагувати можна лише чернетки.
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
                  {order ? outboundNumber(order.outbound_order_id) : 'Буде присвоєно автоматично'}
                  <Lock size={13} aria-hidden />
                </div>
              </Field>
              <Field label="Склад">
                <div className={styles.locked}>
                  {warehouseName}
                  <Lock size={13} aria-hidden />
                </div>
              </Field>

              <Field label="Одержувач *" htmlFor="recipient" error={errors.recipient} wide>
                <select
                  id="recipient"
                  className={cx(
                    styles.control,
                    styles.select,
                    errors.recipient && styles.invalid,
                    !header.recipientId && styles.placeholder,
                  )}
                  value={header.recipientId}
                  onChange={(event) => setField('recipientId', event.target.value)}
                  disabled={readOnly}
                  aria-invalid={errors.recipient ? true : undefined}
                >
                  <option value="">{recipientsQuery.isPending ? 'Завантаження…' : 'Оберіть одержувача'}</option>
                  {recipients.map((recipient) => (
                    <option key={recipient.id} value={recipient.id}>
                      {recipient.company_name}
                    </option>
                  ))}
                  {header.recipientId && !recipientKnown && !recipientsQuery.isPending && (
                    <option value={header.recipientId}>Одержувач №{header.recipientId}</option>
                  )}
                </select>
                {!readOnly && (
                  <Link to="/directories/recipients/new" className={styles.addLink}>
                    + Новий одержувач
                  </Link>
                )}
              </Field>

              <Field label="Дата відвантаження *" htmlFor="date" error={errors.date} wide>
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
                  placeholder="Відвантаження зі зони відвантаження, ворота 2"
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
              <div className={cx(styles.line, styles.lineOutbound, styles.lineHead)} role="row">
                <span role="columnheader">Товар (SKU або назва)</span>
                <span role="columnheader">Кількість</span>
                <span role="columnheader">Од. виміру</span>
                <span role="columnheader">Пакування</span>
                <span role="columnheader">Доступний залишок</span>
                <span />
              </div>

              {lines.map((line, index) => {
                const lineErrors: LineErrors = {
                  ...errors.lines[line.key],
                  product:
                    errors.lines[line.key]?.product ??
                    (duplicateKeys.has(line.key) ? DUPLICATE(line.packageType) : undefined),
                };
                const short = isShort(line);
                return (
                  <div
                    key={line.key}
                    className={cx(styles.line, styles.lineOutbound, short && styles.lineShort)}
                    role="row"
                  >
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
                        className={cx(styles.control, styles.small, (lineErrors.quantity || short) && styles.invalid)}
                        inputMode="decimal"
                        placeholder="0"
                        value={line.quantity}
                        onChange={(event) => updateLine(line.key, { quantity: event.target.value })}
                        disabled={readOnly}
                        aria-label={`Кількість, позиція ${index + 1}`}
                        aria-invalid={lineErrors.quantity || short ? true : undefined}
                      />
                      {lineErrors.quantity ? (
                        <span className={styles.cellError}>{lineErrors.quantity}</span>
                      ) : (
                        short && <span className={styles.cellError}>Більше за залишок</span>
                      )}
                    </div>
                    <div className={styles.cell} role="cell" data-label="Од. виміру">
                      <span className={cx(styles.readout, styles.small)} title="Одиниця виміру товару з каталогу">
                        {line.product ? unitLabel(line.product) : '—'}
                      </span>
                    </div>
                    <div className={styles.cell} role="cell" data-label="Пакування">
                      <select
                        className={cx(styles.control, styles.select, styles.small, styles.selectSmall)}
                        value={line.packageType}
                        onChange={(event) => updateLine(line.key, { packageType: event.target.value as PackageType })}
                        disabled={readOnly}
                        aria-label={`Пакування, позиція ${index + 1}`}
                      >
                        {PACKAGES.map((pkg) => (
                          <option key={pkg} value={pkg}>
                            {PACKAGE_LABELS[pkg]}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className={styles.cell} role="cell" data-label="Доступний залишок">
                      <StockCell
                        product={line.product}
                        available={availableFor(line)}
                        loading={stockQuery.isPending && stockQuery.fetchStatus !== 'idle'}
                        unavailable={stock === null || stockQuery.isError || readOnly}
                        short={short}
                      />
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

            <p className={styles.footnote}>
              {stock === null
                ? 'Залишки поки недоступні: сервер ще не веде облік залишків складу.'
                : stockQuery.isError
                  ? 'Не вдалося завантажити залишки складу.'
                  : `Доступний залишок показано по складу ${warehouseName} на поточний момент.`}
            </p>
          </section>
        </div>

        {}
        <aside className={cx(styles.card, styles.aside)}>
          <h2 className={styles.cardTitle}>Підсумок</h2>
          <dl className={styles.totals}>
            <div className={styles.totalRow}>
              <dt>Позицій</dt>
              <dd>{summary.positions}</dd>
            </div>
            <div className={styles.totalRow}>
              <dt>Усього одиниць</dt>
              <dd>{amountFormat.format(summary.units)} од.</dd>
            </div>
          </dl>
          {shortCount > 0 && (
            <div className={cx(styles.notice, styles.noticeWarn)}>
              <AlertTriangle size={15} aria-hidden />
              <p>
                {shortCount} {plural(shortCount, ['позиція перевищує', 'позиції перевищують', 'позицій перевищують'])}{' '}
                доступний залишок. Чернетку зберегти можна, але провести накладну не вийде.
              </p>
            </div>
          )}
        </aside>
      </div>

      {}
      <div className={cx(styles.card, styles.actions)}>
        <Button variant="cancel" onClick={() => navigate('/orders')}>
          Скасувати
        </Button>
        <div className={styles.actionsRight}>
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
            disabled={readOnly || postMutation.isPending || !header.recipientId || lines.some((l) => !l.product)}
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

function StockCell({
  product,
  available,
  loading,
  unavailable,
  short,
}: {
  product: Product | null;
  available: number | null;
  loading: boolean;
  unavailable: boolean;
  short: boolean;
}) {
  if (!product) return <span className={cx(styles.stock, styles.stockMuted)}>—</span>;
  if (loading) {
    return (
      <span className={cx(styles.stock, styles.stockMuted)}>
        <Loader size={13} className="spin" aria-label="Завантаження залишку" />
      </span>
    );
  }
  if (unavailable || available === null) {
    return (
      <span className={cx(styles.stock, styles.stockMuted)} title="Залишки поки недоступні">
        —
      </span>
    );
  }
  const text = `${amountFormat.format(available)} ${unitLabel(product)}`;
  return short ? (
    <span className={cx(styles.stock, styles.stockShort)}>
      <AlertTriangle size={13} aria-hidden /> {text}
    </span>
  ) : (
    <span className={cx(styles.stock, styles.stockOk)}>
      <Check size={13} aria-hidden /> {text}
    </span>
  );
}
