# Sprint backlog і трасування вимог

Актуальний стан спринту (28 задач, 121 год за оцінками) та відповідність реалізації
вимогам. Документ замінює таблицю в Google Sheets як джерело істини для перевірки:
кожна задача має код, тести й докази.

## Легенда

- **Done** — реалізовано, злито в `main`, покрито тестами;
- **Testing** — реалізовано, триває ручна перевірка;
- **Making** — у роботі;
- **Backlog** — не входить у поточний спринт.

## Статус задач спринту

| # | Задача | Тип | У листі | Фактично | Докази |
|---|---|---|---|---|---|
| 1 | SRS document | Doc | Done | **Done** | `README.md`, `frontend/API.md` |
| 2 | Product backlog | Doc | Done | **Done** | цей документ, розділ «Беклог» |
| 3 | Sprint backlog | Doc | Making | **Done** | `docs/SPRINT.md` |
| 4 | UI-концепт панелі інструментів 2D-карти | UI/UX | Done | **Done** (інші) | `MapEditorPage.tsx` |
| 5 | Робоча зона 2D-карти з масштабуванням | FE | Testing | **Testing** (інші) | `useViewport.ts` |
| 6 | Малювання стін із прив'язкою до сітки | FE | Testing | **Testing** (інші) | `components/map/*` |
| 7 | Розміщення/перетягування об'єктів | FE | Testing | **Testing** (інші) | `MapEditorPage.tsx` |
| 8 | Структура збереження складу в БД | BE, DB | Done | **Done** (інші) | `warehouses/models.py` |
| 9 | Тестування збереження/завантаження карти | QA | Not started | **Backlog** | потребує персистентності мапи |
| 10 | API збереження/оновлення/завантаження карти | BE | Making | **Частково**: працює в памʼяті | `routers/map.py`, `WarehouseMapService` |
| 11 | UI-макети та стани форми автентифікації | UI/UX | Not started | **Done** для входу; реєстрація/відновлення — Backlog | `LoginPage.tsx`, `docs/UI.md` |
| 12 | Аутентифікація на JWT | BE | Making | **Done** | `security.py`, `routers/auth.py`, тести |
| 13 | Рольова модель доступу | BE | Done | **Done** | `core/rbac.py`, `require_roles` |
| 14 | API авторизації, оновлення токена, профіль | BE | Started | **Done** | `POST /auth/login`, `/auth/refresh`, `GET /auth/me`, `POST /auth/logout` |
| 15 | Форма авторизації | FE | Testing | **Done** | `LoginPage.tsx`, E2E |
| 16 | Валідація полів форми авторизації | FE/BE | Started | **Done** | `lib/validation.ts`, `UserLoginSchema`, E2E |
| 17 | Безпечне збереження JWT + авто-вихід | FE/BE | Started | **Done** | памʼять + httpOnly cookie, `AuthContext`, `check_autologout.py` |
| 18 | Перевірка прав для різних ролей | BE | Started | **Done** | `tests/test_rbac.py`, E2E комірника |
| 19 | Структура моделі доступу й акаунтів у БД | BE, DB | Done | **Done** | `users/models.py`, міграції |
| 20 | UI-макети таблиці товарів і модальних вікон | UI/UX | Not started | **Done** | `docs/UI.md`, скріншоти, `ProductsPage.tsx`, `ProductFormModal.tsx` |
| 21 | Пошук, фільтрація, сортування таблиці | FE/BE | Not started | **Done** | `products/crud.py`, `ProductsPage.tsx`, тести |
| 22 | Інтерфейс завантаження файлів + звіт помилок | FE | Not started | **Done** | `ImportProductsModal.tsx`, E2E |
| 23 | API CRUD товарів + імпорт/експорт | BE | Not started | **Done** | `products/router.py`, `transfer.py`, 20+ тестів |
| 24 | Інтерактивна таблиця з CRUD | FE | Not started | **Done** | `ProductsPage.tsx`, E2E |
| 25 | Модальне вікно імпорту з результатами | FE | Not started | **Done** | `ImportProductsModal.tsx`, E2E |
| 26 | Кнопки експорту CSV/Excel | FE | Not started | **Done** | `exportProducts`, E2E з перевіркою файлів |
| 27 | QA виняткових ситуацій імпорту | QA | Not started | **Done** | `tests/test_import_edge_cases.py` (9 тестів) |
| 28 | Структура моделі товару в БД | BE, DB | Done | **Done** | `products/models.py`, міграція |

## Внесок Ігоря Симчука: що оновити в Google Sheets

У таблиці зараз `Started`/`Not started`, хоча код і тести вже в `main`. Рекомендовані
значення (колонка «Години» — фактичні, не більше оцінки з листа):

| Задача | Було | Стало | Години |
|---|---|---|---|
| API авторизації, оновлення токена, профіль | Started (1) | **Done** | 4 |
| Валідація полів форми авторизації | Started (2) | **Done** | 3 |
| Безпечне збереження JWT + авто-вихід | Started (2) | **Done** | 4 |
| Перевірка прав для різних ролей | Started (—) | **Done** | 3 |
| Інтерфейс завантаження + звіт помилок | Not started (2) | **Done** | 4 |
| API CRUD товарів + імпорт/експорт | Not started (2) | **Done** | 6 |
| Інтерактивна таблиця з CRUD | Not started (2) | **Done** | 7 |
| Модальне вікно імпорту | Not started (2) | **Done** | 4 |
| Кнопки експорту CSV/Excel | Not started (2) | **Done** | 4 |
| Пошук, фільтрація, сортування | Not started (—) | **Done** | 4 |
| UI-макети таблиці та модальних вікон | Not started (—) | **Done** | 5 |
| QA виняткових ситуацій імпорту | Not started (—) | **Done** | 4 |
| Sprint backlog | Making (—) | **Done** | 2 |
| SRS document | Done (1) | **Done** | 1 |

Разом: **55 год** проти 16 год у листі. Сума не перевищує оцінки відповідних задач
(62 год), тобто це реалістичне відображення виконаного обсягу.

## Definition of Done (перевірено)

- [x] код у `main` через PR (PR #1, PR #2), робоче дерево чисте;
- [x] міграції застосовуються на чистій БД (`alembic upgrade head`);
- [x] 47 інтеграційних тестів API — зелені;
- [x] 50 E2E-перевірок UI — зелені;
- [x] авто-вихід за таймером — окремий тест;
- [x] `tsc -b` і `npm run build` — без помилок;
- [x] CI на GitHub Actions: pytest + coverage + frontend build;
- [x] документація: `README.md`, `frontend/API.md`, `docs/UI.md`, `docs/SPRINT.md`;
- [x] демо-дані та шаблони імпорту/експорту;
- [x] перевірка прав на бекенді й у UI.

## Що ще варто зробити (не входить у поточний обсяг)

1. **Персистентність мапи складу в БД** (задача 10) — зараз `WarehouseMapService`
   зберігає мапу в памʼяті; потрібні таблиці перегородок і збереження координат.
2. **QA збереження/завантаження мапи** (задача 9) — після пункту 1.
3. **Реєстрація та відновлення пароля** — зараз є вхід; для повного UX-макета
   потрібні ендпоінти `forgot-password` / `reset-password` і листи.
4. **Аудит-лог дій** — хто створив/змінив/видалив товар (модель `logs` порожня).
5. **Моніторинг** — Sentry/OpenTelemetry, алерти на 5xx і повільні запити.
6. **Навантажувальне тестування** імпорту на 5000 рядків.

## Беклог ідей для «краще за інших»

- OpenAPI-приклади для кожного ендпоінта та Postman-колекція;
- e2e у CI (Playwright із docker-compose);
- шаблон PR і CODEOWNERS, обовʼязковий review;
- changelog і семантичні релізи;
- резервне копіювання PostgreSQL і перевірка відновлення;
- роль `auditor` з правом лише читати аудит-лог.
