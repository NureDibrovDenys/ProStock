# ProStock

[![CI](https://github.com/NureDibrovDenys/ProStock/actions/workflows/ci.yml/badge.svg)](https://github.com/NureDibrovDenys/ProStock/actions/workflows/ci.yml) [![Backend tests](https://img.shields.io/badge/pytest-59%20passed-brightgreen)](backend/tests) [![E2E](https://img.shields.io/badge/e2e-50%20passed-brightgreen)](frontend/e2e)

Система управління складом: FastAPI + PostgreSQL на бекенді, React 19 + TypeScript
на фронтенді. Цей етап додає повноцінну авторизацію, керування товарами,
імпорт/експорт каталогу та рольовий доступ.

## Що реалізовано

### Авторизація та сесії
- `POST /api/v1/auth/login` — вхід за email і паролем (перевірка з БД, bcrypt);
- `POST /api/v1/auth/refresh` — оновлення access-токена з **ротацією** refresh-токена;
- `POST /api/v1/auth/logout` — відкликання сесії;
- `GET /api/v1/auth/me` — профіль, роль і набір прав.

Безпека:
- access-токен (15 хв, налаштовується) живе **лише в памʼяті** фронтенду — не в `localStorage`;
- refresh-токен (7 днів) — у **httpOnly** cookie з `SameSite=Lax` і `Path=/api/v1/auth`;
- у БД зберігається тільки SHA-256 хеш refresh-токена;
- статус користувача перевіряється на кожному запиті — блокування діє негайно;
- обмеження спроб входу (10 / 5 хв) і однакова відповідь для невідомого email та
  неправильного пароля;
- авто-вихід на фронтенді: тихий refresh за 60 с до завершення токена, вихід при
  невдалому refresh, після 401 або при втраті cookie. Вихід синхронізується між вкладками.

### Валідація форми входу
- формат email, довжина й складність пароля — на клієнті (підсвітка полів, блокування
  submit, підказка Caps Lock) і на сервері (Pydantic, `422` з переліком полів);
- обробка `401`, `403` (заблокований), `429` (забагато спроб).

### Товари
- CRUD: `GET/POST /products`, `GET/PATCH/DELETE /products/{id}`;
- пошук за SKU/назвою, фільтри за категорією й одиницею виміру, сортування, пагінація;
- категорії: `GET/POST/PATCH/DELETE /categories` (захист від видалення непорожньої);
- інтерактивна таблиця з модальними вікнами створення/редагування, підтвердженням
  видалення та станами завантаження/помилки/порожнього каталогу.

### Імпорт та експорт
- `POST /products/import` — `.csv` або `.xlsx` до 5 МБ / 5000 рядків;
  - обовʼязкові колонки: `sku_code, name, category, unit_of_measure, width, length, height, weight`;
  - існуючі артикули оновлюються, нові створюються, невідомі категорії створюються;
  - коректні рядки зберігаються навіть при помилках в інших;
  - звіт: `total / created / updated / failed / categories_created` + помилки
    `{row, sku_code, field, message}`;
- модальне вікно імпорту: drag&drop, перевірка розміру/формату, підсумок, таблиця
  помилок і вивантаження звіту у CSV;
- шаблони: `GET /products/import/template?format=csv|xlsx`;
- експорт: `GET /products/export?format=csv|xlsx` з урахуванням поточних фільтрів;
  CSV — UTF-8 BOM і `;` (коректно відкривається в Excel), XLSX — зі стилями й фільтром.

### Склад і карта
- `GET /warehouses/{id}` — картка складу;
- `GET /warehouses/{id}/dashboard` — KPI: стелажі, зони, заповненість, вільна площа, останні операції;
- `GET /warehouses/{id}/racks` і `/racks/{code}` — заповненість стелажів і полиці;
- `GET/PUT /warehouses/{id}/map` — топологія з конструктора; зберігається **в БД**
  (JSON-знімок + синхронізація стелажів, зон, перешкод, стін і точок входу).

### Рольовий доступ (RBAC)
| Дія | root | administrator | warehouse_manager | storekeeper | guest |
|---|---|---|---|---|---|
| Читання товарів / експорт | + | + | + | + | + |
| Створення / редагування | + | + | + | – | – |
| Видалення | + | + | – | – | – |
| Імпорт | + | + | + | – | – |
| Користувачі | + | + | – | – | – |
| Мапа складу (запис) | + | + | + | – | – |

Права перевіряються на бекенді; фронтенд ховає недоступні дії та маршрути
(`RequirePermission`) і показує режим перегляду.

## Швидкий старт (Docker)

```bash
cp .env.example .env
# обовʼязково задайте SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"

docker compose up --build
```

- веб-панель — http://localhost:5173
- API / Swagger — http://localhost:8000/docs

Міграції застосовуються автоматично під час старту контейнера бекенда.

### Стартові облікові записи

| Роль | Email | Пароль |
|---|---|---|
| Адміністратор | `admin@prostock.com` | `Admin12345` |
| Менеджер складу | `manager@prostock.com` | `Manager12345` |
| Комірник | `worker@prostock.com` | `Worker12345` |

> Для production: змініть паролі через `.env` (`ADMIN_PASSWORD`, …) або вимкніть
> автозаповнення (`SEED_DEFAULT_USERS=false`) після створення власних акаунтів,
> увімкніть `COOKIE_SECURE=true` (HTTPS) і задайте надійний `SECRET_KEY`.

## Локальна розробка

### Бекенд

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env      # заповніть DB_* та SECRET_KEY
alembic upgrade head
python -m scripts.seed_demo   # необовʼязково: 9 демо-товарів у 3 категоріях
uvicorn app.main:app --reload --port 8000
```

Потрібен PostgreSQL 16. Ролі та стартові користувачі створюються автоматично під час
старту застосунку (ідемпотентно). `scripts/seed_demo.py` також ідемпотентний.

### Фронтенд

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, /api проксюється на :8000
npm run build        # tsc -b + vite build
```

## Тести

```bash
# Бекенд: 59 інтеграційних тестів (окрема БД, ASGI-транспорт)
createdb prostock_test           # або: psql -c "CREATE DATABASE prostock_test"
cd backend && .venv/bin/python -m pytest -q

# E2E у браузері (потрібні запущені бекенд і фронтенд; сценарій самодостатній)
python3 -m pip install playwright && python3 -m playwright install chromium
python3 frontend/e2e/check_ui.py            # 50 перевірок

# Авто-вихід за таймером (бекенд із ACCESS_TOKEN_EXPIRE_MINUTES=1)
python3 frontend/e2e/check_autologout.py    # див. frontend/e2e/README.md
```

Перевірено: 59 pytest-тестів API, 50 E2E-перевірок UI,
авто-вихід за таймером, `npm ci && npm run build`, `alembic upgrade head` на чистій БД.

## Структура

```
backend/
  app/
    core/          конфігурація, БД, enum-и, RBAC, bootstrap, парольна політика
    users/         моделі Role/User/RefreshToken, CRUD, REST, схеми
    products/      моделі, CRUD, імпорт/експорт (CSV/XLSX), REST, схеми
    routers/       auth, map
    warehouses/    картка складу, стелажі, дашборд, сервіс топології
    utils/         JWT/паролі/рольові залежності, rate limiter
  alembic/         міграції (остання — refresh_token)
  tests/           pytest-інтеграційні тести
  scripts/         seed_demo.py — ідемпотентний демо-каталог
frontend/
  src/api/         HTTP-клієнт із refresh-логікою, типи, виклики
  src/auth/        AuthProvider (авто-refresh/вихід), RequireAuth, RequirePermission
  src/pages/       Login, Products, Employees, NewEmployee, склад
  src/components/  Modal, ProductFormModal, ImportProductsModal, ConfirmDialog, UI
  e2e/             Playwright-сценарій
```

Детальний контракт API — [frontend/API.md](frontend/API.md).
UI-специфікація та скріншоти — [docs/UI.md](docs/UI.md).
Стан спринту й трасування вимог — [docs/SPRINT.md](docs/SPRINT.md).

## Відомі обмеження

- реєстрація та відновлення пароля (є лише вхід);
- привʼязка користувача до складу (`warehouse_id`) приймається API, але в моделі ще не зберігається;
- посада та облік змін (`position`, `on_shift`) поки що не зберігаються;
- аудит-лог дій (модель `logs` порожня) і місце зберігання товару на полиці.
