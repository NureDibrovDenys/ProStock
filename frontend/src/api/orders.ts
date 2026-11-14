// Накладні: прихідні (Inbound Order) і вихідні (Outbound Order).
import { ApiError, request } from './client';
import type {
  CapacityCheck,
  InboundOrder,
  InboundOrderItemPayload,
  InboundOrderPayload,
  OrderStatus,
  OutboundOrder,
  OutboundOrderPayload,
  PackageType,
  StockLevel,
} from './types';

const INBOUND = '/inbound-orders';
const OUTBOUND = '/outbound-orders';

/** GET /api/v1/inbound-orders */
export const getInboundOrders = (query: { search?: string; order_status?: OrderStatus; page_size?: number } = {}) =>
  request<InboundOrder[]>(INBOUND, { query });

/** GET /api/v1/inbound-orders/{id} */
export const getInboundOrder = (orderId: number) => request<InboundOrder>(`${INBOUND}/${orderId}`);

/** POST /api/v1/inbound-orders — нова накладна створюється як чернетка. */
export const createInboundOrder = (payload: InboundOrderPayload) =>
  request<InboundOrder>(INBOUND, { method: 'POST', body: payload });

/** PATCH /api/v1/inbound-orders/{id} — рядки (items) замінюються повністю. */
export const updateInboundOrder = (orderId: number, payload: Partial<InboundOrderPayload>) =>
  request<InboundOrder>(`${INBOUND}/${orderId}`, { method: 'PATCH', body: payload });

/**
 * Перевірка вміщуваності партії (FR-4.9, FR-4.10).
 *
 * Ендпоінта ще немає — розрахунок заповненості полиць у беклозі окремою задачею.
 * Запропонований контракт: POST /api/v1/inbound-orders/capacity-check { items } → CapacityCheck.
 * Поки бекенд відповідає 404/405, повертаємо null, і форма показує, що перевірка недоступна.
 */
export async function checkInboundCapacity(items: InboundOrderItemPayload[]): Promise<CapacityCheck | null> {
  try {
    return await request<CapacityCheck>(`${INBOUND}/capacity-check`, { method: 'POST', body: { items } });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 405)) return null;
    throw error;
  }
}

// ── Вихідні накладні ──────────────────────────────────────────────────────
// Ендпоінтів ще немає (задача беклогу «Створити API вихідних накладних з перевіркою залишків»).
// Запропонований контракт повторює прихідні: /api/v1/outbound-orders, PATCH замінює items повністю,
// нова накладна — чернетка, invoice_number бекенд генерує сам.

/** GET /api/v1/outbound-orders/{id} */
export const getOutboundOrder = (orderId: number) => request<OutboundOrder>(`${OUTBOUND}/${orderId}`);

/** POST /api/v1/outbound-orders — нова накладна створюється як чернетка. */
export const createOutboundOrder = (payload: OutboundOrderPayload) =>
  request<OutboundOrder>(OUTBOUND, { method: 'POST', body: payload });

/** PATCH /api/v1/outbound-orders/{id} — рядки (items) замінюються повністю. */
export const updateOutboundOrder = (orderId: number, payload: Partial<OutboundOrderPayload>) =>
  request<OutboundOrder>(`${OUTBOUND}/${orderId}`, { method: 'PATCH', body: payload });

/**
 * Доступні залишки товарів на складі поточного користувача.
 *
 * Обліку залишків на бекенді ще немає. Запропонований контракт:
 * GET /api/v1/stock?product_ids=1,2,3 → StockLevel[] (товар без залишку — available "0").
 * Поки бекенд відповідає 404/405, повертаємо null, і форма показує, що залишки недоступні.
 */
export async function getAvailableStock(productIds: number[]): Promise<Map<number, number> | null> {
  try {
    const levels = await request<StockLevel[]>('/stock', { query: { product_ids: productIds.join(',') } });
    const result = new Map<number, number>(productIds.map((id) => [id, 0]));
    for (const level of levels) result.set(level.product_id, Number(level.available));
    return result;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 405)) return null;
    throw error;
  }
}

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  draft: 'Чернетка',
  in_progress: 'В обробці',
  ready: 'Сформовано завдання',
  completed: 'Завершено',
  canceled: 'Скасовано',
};

export const PACKAGE_LABELS: Record<PackageType, string> = {
  box: 'Коробка',
  pallet: 'Палета',
};

/** Внутрішній номер накладної для відображення: 42 → «ПН-000042». */
export const inboundNumber = (orderId: number) => `ПН-${String(orderId).padStart(6, '0')}`;

/** Внутрішній номер вихідної накладної: 42 → «ВН-000042». */
export const outboundNumber = (orderId: number) => `ВН-${String(orderId).padStart(6, '0')}`;
