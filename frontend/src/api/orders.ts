import { request } from './client';
import type {
  CapacityCheck,
  InboundOrder,
  InboundOrderItemPayload,
  InboundOrderPayload,
  OrderListResponse,
  OrderStatus,
  OrderType,
  OutboundOrder,
  OutboundOrderPayload,
  PackageType,
  PostOrderResult,
  StockLevel,
} from './types';

const INBOUND = '/inbound-orders';
const OUTBOUND = '/outbound-orders';

export const getInboundOrders = (query: { search?: string; order_status?: OrderStatus; page_size?: number } = {}) =>
  request<InboundOrder[]>(INBOUND, { query });

export const getInboundOrder = (orderId: number) => request<InboundOrder>(`${INBOUND}/${orderId}`);

export const createInboundOrder = (payload: InboundOrderPayload) =>
  request<InboundOrder>(INBOUND, { method: 'POST', body: payload });

export const updateInboundOrder = (orderId: number, payload: Partial<InboundOrderPayload>) =>
  request<InboundOrder>(`${INBOUND}/${orderId}`, { method: 'PATCH', body: payload });

export const postInboundOrder = (orderId: number) =>
  request<PostOrderResult>(`${INBOUND}/${orderId}/post`, { method: 'POST' });

export const checkInboundCapacity = (warehouseId: number, items: InboundOrderItemPayload[]) =>
  request<CapacityCheck>(`${INBOUND}/capacity-check`, {
    method: 'POST',
    query: { warehouse_id: warehouseId },
    body: { items },
  });

export const getOutboundOrders = (query: { search?: string; order_status?: OrderStatus; page_size?: number } = {}) =>
  request<OutboundOrder[]>(OUTBOUND, { query });

export const getOutboundOrder = (orderId: number) => request<OutboundOrder>(`${OUTBOUND}/${orderId}`);

export const createOutboundOrder = (payload: OutboundOrderPayload) =>
  request<OutboundOrder>(OUTBOUND, { method: 'POST', body: payload });

export const updateOutboundOrder = (orderId: number, payload: Partial<OutboundOrderPayload>) =>
  request<OutboundOrder>(`${OUTBOUND}/${orderId}`, { method: 'PATCH', body: payload });

export const postOutboundOrder = (orderId: number) =>
  request<PostOrderResult>(`${OUTBOUND}/${orderId}/post`, { method: 'POST' });

export interface OrdersQuery {
  order_type?: OrderType;
  order_status?: OrderStatus;
  search?: string;
  warehouse_id?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export const getOrders = (query: OrdersQuery = {}) =>
  request<OrderListResponse>('/orders', { query: query as Record<string, string | number | boolean | null | undefined> });

export async function getAvailableStock(
  productIds: number[],
  warehouseId?: number | null,
): Promise<Map<number, number>> {
  if (productIds.length === 0) return new Map();
  const levels = await request<StockLevel[]>('/stock', {
    query: { product_ids: productIds.join(','), warehouse_id: warehouseId ?? undefined },
  });
  const result = new Map<number, number>(productIds.map((id) => [id, 0]));
  for (const level of levels) result.set(level.product_id, Number(level.available));
  return result;
}

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  draft: 'Чернетка',
  in_progress: 'В обробці',
  ready: 'Сформовано завдання',
  completed: 'Завершено',
  canceled: 'Скасовано',
};

export const ORDER_TYPE_LABELS: Record<OrderType, string> = {
  inbound: 'Прихідна',
  outbound: 'Вихідна',
};

export const PACKAGE_LABELS: Record<PackageType, string> = {
  box: 'Коробка',
  pallet: 'Палета',
};

export const inboundNumber = (orderId: number) => `ПН-${String(orderId).padStart(6, '0')}`;

export const outboundNumber = (orderId: number) => `ВН-${String(orderId).padStart(6, '0')}`;
