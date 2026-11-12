import { useQuery } from '@tanstack/react-query';
import { useSyncExternalStore } from 'react';
import { isAdminRole } from '../api/users';
import { getWarehouses } from '../api/warehouse';
import { useAuth } from '../auth/AuthContext';

// Адміністратор не прив'язаний до складу — поточний склад він обирає перемикачем у навбарі.
// Вибір зберігається в localStorage, щоб пережити перезавантаження й бути спільним для вкладок.
const STORAGE_KEY = 'prostock.currentWarehouse';
const listeners = new Set<() => void>();
/** Запасне сховище, якщо localStorage недоступний (приватний режим). */
let memoryValue: number | null = null;

function readSelection(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) ? id : null;
  } catch {
    return memoryValue;
  }
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) onChange();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener('storage', onStorage);
  };
}

/** Робить склад поточним для адміністратора (мапа, співробітники, дашборд). */
export function selectWarehouse(warehouseId: number) {
  memoryValue = warehouseId;
  try {
    localStorage.setItem(STORAGE_KEY, String(warehouseId));
  } catch {
    // працюємо з memoryValue до перезавантаження
  }
  listeners.forEach((listener) => listener());
}

/** Усі склади (GET /warehouses доступний лише адміністратору). */
export function useWarehouses(enabled = true) {
  return useQuery({ queryKey: ['warehouses'], queryFn: getWarehouses, enabled });
}

/**
 * ID поточного складу або null, якщо його немає.
 * • Менеджер і комірник — склад із профілю.
 * • Адміністратор — обраний перемикачем; якщо вибору немає або склад видалено — перший зі списку.
 */
export function useCurrentWarehouse(): number | null {
  const { session } = useAuth();
  const isAdmin = isAdminRole(session?.user.role);
  const selected = useSyncExternalStore(subscribe, readSelection);
  const warehouses = useWarehouses(isAdmin);

  if (!isAdmin) return session?.user.warehouse_id ?? null;

  const list = warehouses.data;
  // Поки список вантажиться, довіряємо збереженому вибору, щоб сторінки не блимали «Склад не обрано»
  if (!list) return selected;
  if (selected !== null && list.some((w) => w.warehouse_id === selected)) return selected;
  return list[0]?.warehouse_id ?? null;
}
