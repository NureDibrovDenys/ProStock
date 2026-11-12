// Вибір поточного складу адміністратором.
//
// Це лише ідентифікатор (не чутливі дані), тому він зберігається в localStorage —
// вибір переживає перезавантаження сторінки. Access-токен, як і раніше, живе
// тільки в памʼяті (див. src/api/client.ts).
import { useSyncExternalStore } from 'react';

const STORAGE_KEY = 'prostock.warehouseId';

function read(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  } catch {
    // localStorage може бути недоступний (приватний режим)
    return null;
  }
}

let selected: number | null = read();
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getSelectedWarehouse(): number | null {
  return selected;
}

/** null — скинути вибір (наприклад, після виходу з акаунта). */
export function setSelectedWarehouse(warehouseId: number | null): void {
  if (warehouseId === selected) return;
  selected = warehouseId;
  try {
    if (warehouseId === null) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, String(warehouseId));
  } catch {
    // без localStorage вибір просто не переживе перезавантаження
  }
  emit();
}

/** Реактивне значення вибраного складу. */
export function useSelectedWarehouse(): number | null {
  return useSyncExternalStore(subscribe, getSelectedWarehouse, getSelectedWarehouse);
}

// Вибір синхронізується між вкладками, як і вихід із сесії
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== STORAGE_KEY) return;
    selected = read();
    emit();
  });
}
