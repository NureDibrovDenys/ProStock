// Довідники постачальників і одержувачів: /api/v1/suppliers і /api/v1/recipients
// (backend/app/counterparties). Решта фронтенду працює з типом Counterparty.
import { request } from './client';
import type { Counterparty, CounterpartyInput, CounterpartyKind, CounterpartyStatus } from './types';

/** Відповідь бекенду: SupplierRead / RecipientRead. Ідентифікатор має префікс сутності. */
interface ApiCounterparty {
  supplier_id?: number;
  recipient_id?: number;
  company_name: string;
  tax_id: string | null;
  contact_person: string | null;
  phone_number: string | null;
  email: string | null;
  address: string | null;
  status: string;
}

interface ApiCounterpartyList {
  items: ApiCounterparty[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Максимум, який дозволяє бекенд; пагінації в інтерфейсі довідників поки немає. */
const PAGE_SIZE = 200;

function fromApi(raw: ApiCounterparty): Counterparty {
  return {
    id: Number(raw.supplier_id ?? raw.recipient_id),
    company_name: raw.company_name,
    tax_id: raw.tax_id,
    contact_person: raw.contact_person,
    phone_number: raw.phone_number,
    email: raw.email,
    address: raw.address,
    status: raw.status.toLowerCase() as CounterpartyStatus,
  };
}

/** GET /api/v1/{suppliers|recipients} */
export const getCounterparties = async (kind: CounterpartyKind) =>
  (await request<ApiCounterpartyList>(`/${kind}`, { query: { page_size: PAGE_SIZE } })).items.map(fromApi);

/** GET /api/v1/{suppliers|recipients}/{id} */
export const getCounterparty = async (kind: CounterpartyKind, id: number) =>
  fromApi(await request<ApiCounterparty>(`/${kind}/${id}`));

/** POST /api/v1/{suppliers|recipients} */
export const createCounterparty = async (kind: CounterpartyKind, data: CounterpartyInput) =>
  fromApi(await request<ApiCounterparty>(`/${kind}`, { method: 'POST', body: data }));

/** PATCH /api/v1/{suppliers|recipients}/{id} — лише змінені поля. */
export const updateCounterparty = async (kind: CounterpartyKind, id: number, data: Partial<CounterpartyInput>) =>
  fromApi(await request<ApiCounterparty>(`/${kind}/${id}`, { method: 'PATCH', body: data }));

/** DELETE /api/v1/{suppliers|recipients}/{id} */
export const deleteCounterparty = (kind: CounterpartyKind, id: number) =>
  request<void>(`/${kind}/${id}`, { method: 'DELETE' });

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
