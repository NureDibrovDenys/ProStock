import type { Shelf } from '../../api/types';

/**
 * Дані однієї етикетки. `qr` кодується в QR-код і дублюється текстом під ним,
 * щоб код можна було ввести вручну, якщо сканер не прочитає мітку.
 */
export interface LabelData {
  qr: string;
  /** Тип мітки дрібним шрифтом над заголовком: «Полиця», «LPN». */
  kind: string;
  title: string;
  lines: string[];
}

export function shelfLabel(shelf: Pick<Shelf, 'qr' | 'shelf_code'>, rackCode: string): LabelData {
  return {
    qr: shelf.qr,
    kind: 'Полиця',
    title: shelf.shelf_code,
    lines: [`Стелаж ${rackCode}`],
  };
}

/**
 * Джерело для етикетки LPN. Бекенд поки не віддає LPN накладної (немає зв'язку
 * lpn_container → inbound_order), тож тип описує, що потрібно від майбутнього
 * ендпоінта GET /orders/inbound/{id}/lpn.
 */
export interface LpnLabelSource {
  /** Код LPN, він же вміст QR. */
  code: string;
  productName: string;
  skuCode: string;
  /** Кількість з одиницею, наприклад «40 уп.». */
  quantity: string;
  orderNumber?: string;
}

export function lpnLabel(lpn: LpnLabelSource): LabelData {
  const lines = [`${lpn.skuCode} · ${lpn.productName}`, lpn.quantity];
  if (lpn.orderNumber) lines.push(lpn.orderNumber);

  return { qr: lpn.code, kind: 'LPN', title: lpn.code, lines };
}
