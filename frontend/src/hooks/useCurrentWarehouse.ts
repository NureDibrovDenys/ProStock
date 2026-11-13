import { useAuth } from '../auth/AuthContext';

/** ID призначеного складу або null, якщо призначення немає */
export function useCurrentWarehouse(): number | null {
  const { session } = useAuth();

  return session?.user.warehouse_id ?? null;
}
