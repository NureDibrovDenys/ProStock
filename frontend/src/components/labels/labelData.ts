import type { LpnContainer, Shelf } from '../../api/types';
import { formatNumber } from '../../lib/format';

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
 * Етикетка коробки. Заголовок - назва товару: код LPN і так надруковано під QR,
 * а комірнику на полиці важливіше одразу бачити, що в коробці.
 */
export function lpnLabel(lpn: LpnContainer, orderNumber: string): LabelData {
  const lines = [lpn.sku_code, `К-сть: ${formatNumber(Number(lpn.quantity))}`];
  if (lpn.shelf_code) lines.push(`Полиця ${lpn.shelf_code}`);
  lines.push(orderNumber);

  return { qr: lpn.code, kind: 'LPN', title: lpn.product_name, lines };
}
