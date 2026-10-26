# PLAN — ProStock: авторизація, товари, імпорт/експорт, RBAC

## 1. Бекенд: авторизація
- [x] Виправити `verify_password` (зараз повертає хеш замість результату перевірки)
- [x] Модель `RefreshToken` + міграція Alembic
- [x] `POST /api/v1/auth/login` — перевірка користувача з БД, видача access + refresh (httpOnly cookie)
- [x] `POST /api/v1/auth/refresh` — ротація refresh-токена, новий access
- [x] `POST /api/v1/auth/logout` — відкликання refresh, очищення cookie
- [x] `GET /api/v1/auth/me` — профіль користувача з БД (email, ім'я, роль, статус)
- [x] Bootstrap ролей і адміністратора за замовчуванням (idempotent)

## 2. Бекенд: RBAC
- [x] Матриця прав за ролями (`require_roles`, `require_permission`)
- [x] Перевірка статусу користувача (blocked/inactive → 403)
- [x] Захист CRUD користувачів (root/admin)
- [x] Захист CRUD товарів (read — усі автентифіковані, write — root/admin/manager, delete — root/admin)

## 3. Бекенд: користувачі
- [x] `users/crud.py` — list/get/create/update/delete з перевіркою унікальності email
- [x] `users/router.py` — REST + пагінація + фільтри
- [x] Валідація email/пароля на сервері (спільні правила з фронтом)

## 4. Бекенд: товари
- [x] `products/schemas.py` — Category/Product/Supplier, валідація полів
- [x] `products/crud.py` — list (search/sort/filter/pagination), get, create, update, delete
- [x] `products/router.py` — REST `/api/v1/products`, `/api/v1/categories`
- [x] Імпорт CSV/XLSX: `POST /api/v1/products/import` зі звітом про помилки по рядках
- [x] Експорт CSV/XLSX: `GET /api/v1/products/export?format=csv|xlsx`

## 5. Фронтенд: авторизація
- [x] Access-токен лише в пам'яті, refresh — httpOnly cookie (безпечне зберігання)
- [x] Тихий refresh при старті та перед завершенням access-токена
- [x] Авто-вихід при закінченні сесії / 401 / невдалому refresh
- [x] Валідація полів форми входу (email, пароль, підсвітка помилок, блокування submit)
- [x] Захищені маршрути + guard за ролями

## 6. Фронтенд: товари
- [x] Сторінка товарів: інтерактивна таблиця (пошук, сортування, пагінація)
- [x] Створення / редагування товару в модальному вікні з валідацією
- [x] Видалення з підтвердженням
- [x] Модальне вікно імпорту: drag&drop, прогрес, звіт про помилки по рядках
- [x] Кнопки експорту CSV та Excel (завантаження файлу)

## 7. Верифікація (результати)
- [x] `alembic upgrade head` на чистій БД
- [x] Інтеграційні тести API (login/refresh/me/RBAC/CRUD/import/export)
- [x] `npm run build` без помилок
- [x] Прогін UI у браузері
- [x] Коміт + push + PR

## Результати перевірки

- `alembic upgrade head` на чистій БД — 15 таблиць, включно з `refresh_token`.
- `pytest` — 33 тести API: auth/refresh/RBAC/CRUD/імпорт/експорт/користувачі.
- Live API smoke — 79 перевірок, 0 помилок.
- Playwright E2E — 49 перевірок UI, 0 помилок (вхід, валідація, CRUD, імпорт зі звітом,
  експорт CSV/XLSX, RBAC, відновлення та завершення сесії).
- `npm run build` (tsc + vite) — успішно.
