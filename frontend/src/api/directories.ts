// Довідники постачальників і одержувачів.
//
// temporary: Backend endpoints do not exist yet, so the pages run on in-memory test data
// When CRUD appears on the backend, the following steps are needed to switch to real API:
//   1) set USE_MOCK = false;
//   2) Check the paths and field names in `fromApi` / `toApi` against the backend schemas
// The rest of the frontend works with the Counterparty type and requires no changes
import { ApiError, request } from './client';
import type { Counterparty, CounterpartyInput, CounterpartyKind, CounterpartyStatus } from './types';

const USE_MOCK = true;

// ── real API ──────────────────────────────────────────────────────────

/** Backend response fields: prefixes as in the columns of the Supplier / Recipient models */
type ApiCounterparty = Record<string, unknown>;

const API_FIELDS = {
  suppliers: { id: 'supplier_id', email: 'supplier_email', address: 'supplier_address', status: 'supplier_status' },
  recipients: { id: 'recipient_id', email: 'recipient_email', address: 'delivery_address', status: 'recipient_status' },
} as const;

function fromApi(kind: CounterpartyKind, raw: ApiCounterparty): Counterparty {
  const f = API_FIELDS[kind];
  return {
    id: Number(raw[f.id] ?? raw.id),
    company_name: String(raw.company_name ?? ''),
    tax_id: (raw.tax_id as string | null) ?? null,
    contact_person: (raw.contact_person as string | null) ?? null,
    phone_number: (raw.phone_number as string | null) ?? null,
    email: ((raw[f.email] ?? raw.email) as string | null) ?? null,
    address: ((raw[f.address] ?? raw.address) as string | null) ?? null,
    status: String(raw[f.status] ?? raw.status ?? 'active').toLowerCase() as CounterpartyStatus,
  };
}

function toApi(kind: CounterpartyKind, data: Partial<CounterpartyInput>): ApiCounterparty {
  const f = API_FIELDS[kind];
  const body: ApiCounterparty = {};
  if (data.company_name !== undefined) body.company_name = data.company_name;
  if (data.tax_id !== undefined) body.tax_id = data.tax_id;
  if (data.contact_person !== undefined) body.contact_person = data.contact_person;
  if (data.phone_number !== undefined) body.phone_number = data.phone_number;
  if (data.email !== undefined) body[f.email] = data.email;
  if (data.address !== undefined) body[f.address] = data.address;
  return body;
}

const api = {
  list: async (kind: CounterpartyKind) =>
    (await request<ApiCounterparty[]>(`/${kind}`)).map((item) => fromApi(kind, item)),
  get: async (kind: CounterpartyKind, id: number) => fromApi(kind, await request<ApiCounterparty>(`/${kind}/${id}`)),
  create: async (kind: CounterpartyKind, data: CounterpartyInput) =>
    fromApi(kind, await request<ApiCounterparty>(`/${kind}`, { method: 'POST', body: toApi(kind, data) })),
  update: async (kind: CounterpartyKind, id: number, data: Partial<CounterpartyInput>) =>
    fromApi(kind, await request<ApiCounterparty>(`/${kind}/${id}`, { method: 'PATCH', body: toApi(kind, data) })),
  remove: (kind: CounterpartyKind, id: number) => request<void>(`/${kind}/${id}`, { method: 'DELETE' }),
};

// ── Тестові дані (з макета) ──────────────────────────────────────────────

const seed = (rows: Array<[string, string, string, string, string | null]>): Counterparty[] =>
  rows.map(([company_name, contact_person, phone_number, address, tax_id], index) => ({
    id: index + 1,
    company_name,
    contact_person,
    phone_number,
    address,
    tax_id,
    email: null,
    status: 'active',
  }));

const store: Record<CounterpartyKind, Counterparty[]> = {
  suppliers: seed([
    ['ТОВ «Агро-Трейд»', 'Олег Савчук', '+380 67 123 45 67', 'м. Київ, вул. Промислова, 12', '30123456'],
    ['ПрАТ «Меблі-Про»', 'Ірина Гнатюк', '+380 50 234 56 78', 'м. Львів, вул. Городоцька, 210', '31234567'],
    ['ТОВ «БудЛайн»', 'Василь Кравчук', '+380 63 345 67 89', 'м. Харків, просп. Гагаріна, 45', '32345678'],
    ['ТОВ «ЕлектроСвіт»', 'Наталія Бойко', '+380 97 456 78 90', 'м. Дніпро, вул. Січеславська, 7', '33456789'],
    ['ФОП Петренко І. В.', 'Іван Петренко', '+380 66 567 89 01', 'м. Одеса, вул. Балківська, 120', '2934567890'],
    ['ТОВ «Укрпак»', 'Андрій Ткач', '+380 68 678 90 12', 'м. Запоріжжя, вул. Заводська, 3', '34567890'],
    ['ТОВ «ХімДім»', 'Світлана Мороз', '+380 99 789 01 23', 'м. Вінниця, вул. Келецька, 58', '35678901'],
    ['ТОВ «ТехноЛогістик»', 'Максим Олійник', '+380 73 890 12 34', 'м. Полтава, вул. Зіньківська, 19', '36789012'],
  ]),
  recipients: seed([
    ['Магазин «Сільпо» №12', 'Олена Руденко', '+380 67 111 22 33', 'м. Київ, вул. Хрещатик, 15', '40720198'],
    ['АТБ-Маркет, філія Львів', 'Петро Гуменюк', '+380 50 222 33 44', 'м. Львів, вул. Наукова, 8', '30487219'],
    ['ТОВ «Епіцентр К»', 'Ганна Литвин', '+380 63 333 44 55', 'м. Харків, вул. Героїв Праці, 9', '32490244'],
    ['ФОП Бондар О. М.', 'Олег Бондар', '+380 97 444 55 66', 'м. Дніпро, вул. Яворницького, 21', null],
  ]),
};

const delay = () => new Promise((resolve) => setTimeout(resolve, 250));

function findOrThrow(kind: CounterpartyKind, id: number): Counterparty {
  const item = store[kind].find((row) => row.id === id);
  if (!item) throw new ApiError(404, kind === 'suppliers' ? 'Постачальника не знайдено' : 'Одержувача не знайдено');
  return item;
}

/** Як у моделі: ЄДРПОУ постачальника унікальний, в одержувачів (філії мережі) — ні. */
function checkUniqueTaxId(kind: CounterpartyKind, taxId: string | null | undefined, exceptId?: number) {
  if (kind !== 'suppliers' || !taxId) return;
  if (store.suppliers.some((row) => row.tax_id === taxId && row.id !== exceptId)) {
    throw new ApiError(409, 'Постачальник з таким ЄДРПОУ / ІПН вже існує');
  }
}

const mock = {
  list: async (kind: CounterpartyKind) => {
    await delay();
    return store[kind].map((row) => ({ ...row }));
  },
  get: async (kind: CounterpartyKind, id: number) => {
    await delay();
    return { ...findOrThrow(kind, id) };
  },
  create: async (kind: CounterpartyKind, data: CounterpartyInput) => {
    await delay();
    checkUniqueTaxId(kind, data.tax_id);
    const id = Math.max(0, ...store[kind].map((row) => row.id)) + 1;
    const item: Counterparty = { ...data, id, status: 'active' };
    store[kind].push(item);
    return { ...item };
  },
  update: async (kind: CounterpartyKind, id: number, data: Partial<CounterpartyInput>) => {
    await delay();
    const item = findOrThrow(kind, id);
    checkUniqueTaxId(kind, data.tax_id, id);
    Object.assign(item, data);
    return { ...item };
  },
  remove: async (kind: CounterpartyKind, id: number) => {
    await delay();
    findOrThrow(kind, id);
    store[kind] = store[kind].filter((row) => row.id !== id);
  },
};

const source = USE_MOCK ? mock : api;

/** GET /api/v1/{suppliers|recipients} */
export const getCounterparties = (kind: CounterpartyKind) => source.list(kind);
/** GET /api/v1/{suppliers|recipients}/{id} */
export const getCounterparty = (kind: CounterpartyKind, id: number) => source.get(kind, id);
/** POST /api/v1/{suppliers|recipients} */
export const createCounterparty = (kind: CounterpartyKind, data: CounterpartyInput) => source.create(kind, data);
/** PATCH /api/v1/{suppliers|recipients}/{id} — лише змінені поля. */
export const updateCounterparty = (kind: CounterpartyKind, id: number, data: Partial<CounterpartyInput>) =>
  source.update(kind, id, data);
/** DELETE /api/v1/{suppliers|recipients}/{id} */
export const deleteCounterparty = (kind: CounterpartyKind, id: number) => source.remove(kind, id);

/** Тексти інтерфейсу для кожного довідника. */
export const DIRECTORY_LABELS: Record<
  CounterpartyKind,
  { title: string; listTitle: string; one: string; accusative: string; nameLabel: string; namePlaceholder: string }
> = {
  suppliers: {
    title: 'Постачальники',
    listTitle: 'Усі постачальники',
    one: 'Постачальник',
    accusative: 'постачальника',
    nameLabel: 'Назва компанії',
    namePlaceholder: 'ТОВ «Агро-Трейд»',
  },
  recipients: {
    title: 'Одержувачі',
    listTitle: 'Усі одержувачі',
    one: 'Одержувач',
    accusative: 'одержувача',
    nameLabel: 'Назва одержувача',
    namePlaceholder: 'Магазин «Сільпо» №12',
  },
};

export const isCounterpartyKind = (value: string | undefined): value is CounterpartyKind =>
  value === 'suppliers' || value === 'recipients';
