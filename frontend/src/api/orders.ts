// Накладні: прихідні (Inbound Order). Вихідні з'являться, коли бекенд додасть API.
import { ApiError, request } from './client';
import type {
  CapacityCheck,
  InboundOrder,
  InboundOrderItemPayload,
  InboundOrderPayload,
  OrderStatus,
  PackageType,
} from './types';

const INBOUND = '/inbound-orders';

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
