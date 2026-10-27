# API ProStock, яке очікує веб-панель

Базовий префікс: `/api/v1`. Формат — JSON. Авторизація — заголовок
`Authorization: Bearer <access_token>`.

Помилки — стандартні для FastAPI: `{"detail": "текст"}` або список помилок
валідації. Текст із `detail` показується користувачу як є.

---

## Авторизація

Схема сесії:

- **access-токен** (JWT, 15 хв) повертається в тілі відповіді. Фронтенд тримає його
  лише в памʼяті — не в `localStorage`;
- **refresh-токен** (JWT, 7 днів) передається в **httpOnly cookie**
  `prostock_refresh` з `Path=/api/v1/auth`, `SameSite=Lax`. JS до нього доступу не має;
- кожен refresh **ротується**: старий токен відкликається, видається новий;
- у БД зберігається лише SHA-256 хеш refresh-токена.

| Метод | Шлях | Опис |
|---|---|---|
| POST | `/auth/login` | Вхід, видає access + refresh |
| POST | `/auth/refresh` | Новий access за refresh-cookie |
| POST | `/auth/logout` | Відкликає refresh, чистить cookie |
| GET | `/auth/me` | Профіль, роль і права поточного користувача |

### POST /auth/login

```json
// запит
{ "email": "admin@prostock.com", "password": "Admin12345" }
// відповідь 200 + Set-Cookie: prostock_refresh=…; HttpOnly; Path=/api/v1/auth
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "user_id": 1,
    "user_email": "admin@prostock.com",
    "first_name": "Адмін",
    "last_name": "Системи",
    "role": "administrator",
    "status": "active",
    "permissions": {
      "products_read": true, "products_write": true, "products_delete": true,
      "products_import": true, "products_export": true,
      "users_manage": true, "warehouse_map_write": true
    }
  }
}
```

Помилки: `401` — невірний email або пароль (однакова відповідь для обох випадків),
`403` — обліковий запис заблоковано, `422` — некоректний формат полів,
`429` — забагато спроб входу (заголовок `Retry-After`).

### GET /auth/me

Повертає той самий об'єкт `user` + `created_at`. Використовується для перевірки,
що сесія ще дійсна.

---

## Права доступу (RBAC)

| Дія | root | administrator | warehouse_manager | storekeeper | guest |
|---|---|---|---|---|---|
| Читання товарів / експорт | + | + | + | + | + |
| Створення / редагування товарів | + | + | + | – | – |
| Видалення товарів | + | + | – | – | – |
| Імпорт товарів | + | + | + | – | – |
| Керування користувачами | + | + | – | – | – |
| Редагування мапи складу | + | + | + | – | – |

Перевірка виконується на бекенді (не лише в UI). Статус користувача перевіряється
на кожному запиті: заблокований втрачає доступ негайно, навіть із дійсним access-токеном.

---

## Користувачі

| Метод | Шлях | Права |
|---|---|---|
| GET | `/users?search=&role=&status=&page=&page_size=` | root, administrator |
| POST | `/users` | root, administrator |
| GET | `/users/{id}` | root, administrator |
| PATCH | `/users/{id}` | root, administrator |
| DELETE | `/users/{id}` | root, administrator |

```json
// POST /users
{
  "first_name": "Іван",
  "last_name": "Петренко",
  "user_email": "i.petrenko@prostock.ua",
  "password": "Temp12345",
  "role": "storekeeper",
  "warehouse_id": 1
}
```

Роль: `root | administrator | warehouse_manager | storekeeper | guest`.
Пароль: 8–128 символів, велика й мала літери, цифра (перевіряється і на фронті, і на сервері).
Відповідь — елемент списку:

```json
{
  "user_id": 5, "user_email": "i.petrenko@prostock.ua",
  "first_name": "Іван", "last_name": "Петренко",
  "role": "storekeeper", "status": "active",
  "position": null, "on_shift": false,
  "created_at": "2026-10-26T13:40:00Z"
}
```

Список — `{ "items": [...], "total": 12, "page": 1, "page_size": 20, "pages": 1 }`.

Помилки: `409` — email зайнятий / спроба видалити себе / останній адміністратор.

---

## Товари

| Метод | Шлях | Права |
|---|---|---|
| GET | `/products` | будь-який автентифікований |
| POST | `/products` | root, administrator, warehouse_manager |
| GET | `/products/{id}` | будь-який автентифікований |
| PATCH | `/products/{id}` | root, administrator, warehouse_manager |
| DELETE | `/products/{id}` | root, administrator |
| POST | `/products/import` | root, administrator, warehouse_manager |
| GET | `/products/import/template?format=csv\|xlsx` | будь-який автентифікований |
| GET | `/products/export?format=csv\|xlsx` | будь-який автентифікований |

### GET /products

Параметри: `search` (SKU або назва), `category_id`, `unit_of_measure`,
`sort_by` (`product_id|sku_code|name|weight|min_stock_level`), `sort_order` (`asc|desc`),
`page`, `page_size` (1–200).

```json
{
  "items": [{
    "product_id": 1, "sku_code": "CHEM-001", "name": "Мило рідке, 1 л",
    "category_id": 1, "category_name": "Побутова хімія",
    "unit_of_measure": "pcs",
    "width": "0.10", "length": "0.10", "height": "0.25",
    "weight": "1.100", "min_stock_level": "10.00"
  }],
  "total": 42, "page": 1, "page_size": 20, "pages": 3
}
```

`unit_of_measure`: `pcs | kg | pound | box | pallet | other`.
Габарити — метри, вага — кілограми.

Помилки: `409` — SKU вже існує, `422` — некоректні поля або категорія.

### POST /products/import

`multipart/form-data`, поле `file` — `.csv` або `.xlsx`, до 5 МБ, до 5000 рядків.

Колонки (регістр не важливий, підтримуються українські назви):
`sku_code, name, category, unit_of_measure, width, length, height, weight, min_stock_level`.

- категорія вказується назвою; невідома створюється автоматично;
- існуючий `sku_code` оновлюється, новий — створюється;
- коректні рядки зберігаються навіть якщо інші містять помилки.

```json
{
  "filename": "products.csv",
  "total": 5, "created": 2, "updated": 1, "failed": 2,
  "categories_created": 1,
  "errors": [
    { "row": 4, "sku_code": "BAD-001", "field": "width", "message": "Некоректне число" },
    { "row": 6, "sku_code": "", "field": "sku_code", "message": "Поле не може бути порожнім" }
  ]
}
```

`row` — номер рядка у файлі (заголовок = 1). Помилки структури файлу → `422`,
завеликий файл → `413`.

### GET /products/export

Повертає файл `products_YYYYMMDD_HHMMSS.csv` (UTF-8 BOM, `;`) або `.xlsx`.
Ті самі фільтри, що й у списку. Заголовок `X-Total-Count` — кількість рядків.

---

## Категорії

| Метод | Шлях | Права |
|---|---|---|
| GET | `/categories` | будь-який автентифікований |
| POST | `/categories` | root, administrator, warehouse_manager |
| PATCH | `/categories/{id}` | root, administrator, warehouse_manager |
| DELETE | `/categories/{id}` | root, administrator |

```json
[ { "category_id": 1, "name": "Побутова хімія", "description": null, "products_count": 2 } ]
```

Видалити категорію з товарами не можна (`409`).

---

## Склад (залишено з попереднього етапу)

| Метод | Шлях | Статус |
|---|---|---|
| GET | `/warehouses/{id}/map` | тимчасово зберігається в памʼяті процесу |
| PUT | `/warehouses/{id}/map` | те саме; відповідь — збережена мапа з `*_id` нових об'єктів |

Формат мапи — `WarehouseMapUpdateSchema` у `backend/app/schemas.py` (приклад — у Swagger):
метри, `coord_x`/`coord_y` — центр об'єкта, `rotation_angle` — градуси за годинниковою стрілкою [0, 360).
`walls` — вершини контуру з `vertex_order` (простий полігон, площа > 0), `partitions` — перегородки
`start_x/start_y/end_x/end_y/thickness/height`, далі `racks`, `obstacles`, `zones`, `entry_points`.
Об'єкти з `*_id` зберігають його, без `*_id` — отримують новий. Числа віддаються числами.
| GET | `/warehouses/{id}`, `/dashboard`, `/racks` | ще не реалізовано |

Усі ці ендпоінти вимагають авторизації; запис мапи — root / administrator / warehouse_manager.

---

## Службові

| Метод | Шлях | Опис |
|---|---|---|
| GET | `/` | перевірка, що API працює |
| GET | `/health` | стан API та підключення до БД |
| GET | `/docs` | Swagger UI |
