// Налаштування застосунку з env-змінних Vite (див. .env.example)

/** Склад, з яким працює веб-панель. Пізніше прийде з профілю менеджера. */
export const WAREHOUSE_ID = Number(import.meta.env.VITE_WAREHOUSE_ID ?? 1);

/** Вхід за паролем вимкнений за замовчуванням, поки йде перевірка функціоналу. */
export const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === 'true';
