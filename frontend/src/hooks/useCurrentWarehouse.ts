import { useAuth } from '../auth/AuthContext';
import { canSwitchWarehouse } from '../lib/roles';
import { useSelectedWarehouse } from './useWarehouseSelection';

/**
 * ID поточного складу або null, якщо склад не визначено.
 *
 * Менеджер і комірник завжди працюють зі складом зі свого профілю.
 * Адміністратор — зі складом, обраним у перемикачі (мапа, дашборд, співробітники);
 * поки вибору немає, береться склад із його профілю, якщо він призначений.
 */
export function useCurrentWarehouse(): number | null {
  const { session } = useAuth();
  const selected = useSelectedWarehouse();
  const own = session?.user.warehouse_id ?? null;

  if (canSwitchWarehouse(session?.user)) return selected ?? own;

  return own;
}
