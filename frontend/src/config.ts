// Налаштування застосунку з env-змінних Vite (див. .env.example)

/** Склад, з яким працює веб-панель. Пізніше прийде з профілю менеджера. */
export const WAREHOUSE_ID = Number(import.meta.env.VITE_WAREHOUSE_ID ?? 1);

/** Вхід увімкнений за замовчуванням; VITE_AUTH_ENABLED=false — лише для локальних експериментів. */
export const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED !== 'false';
