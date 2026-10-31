import { useAuth } from '../auth/AuthContext';

/** Усі користувачі мають робочий склад; старі профілі тимчасово працюють зі складом №1. */
export function useCurrentWarehouse() {
  const { session } = useAuth();
  return session?.user.warehouse_id ?? 1;
}
