# API, яке очікує веб-панель ProStock

Базовий префікс: `/api/v1`. Формат — JSON. Авторизація — заголовок `Authorization: Bearer <JWT>`
(поки вхід на фронті вимкнений, токен може не надсилатися).

Імена полів і значення enum узгоджені з `backend/app/*/models.py` та `backend/app/core/enums.py`.
TypeScript-типи — `src/api/types.ts`, виклики — `src/api/*.ts`.

| Метод | Шлях | Екран | Статус на бекенді |
|---|---|---|---|
| POST | `/auth/login` | Вхід | ✅ є |
| GET | `/warehouses/{id}` | назва складу в заголовках | ❌ |
| GET | `/warehouses/{id}/map` | Склад, Конструктор | ⚠️ є, але старий формат |
| PUT | `/warehouses/{id}/map` | Конструктор | ⚠️ є, але старий формат |
| GET | `/warehouses/{id}/racks` | Склад (заповненість стелажів) | ❌ |
| GET | `/warehouses/{id}/racks/{rack_code}` | Стелаж | ❌ |
| GET | `/warehouses/{id}/dashboard` | Головна | ❌ |
| GET | `/users?warehouse_id={id}` | Співробітники | ❌ |
| POST | `/users` | Новий співробітник | ❌ |

Помилки — стандартні для FastAPI: `{"detail": "текст"}` або список помилок валідації.
Текст із `detail` показується користувачу як є, тому краще писати його українською.

---

## POST /auth/login

```json
// запит
{ "email": "admin@prostock.com", "password": "admin123" }
// відповідь 200
{ "access_token": "<JWT>", "token_type": "bearer" }
```
У payload JWT фронт читає `sub` (email), `role`, `exp`. Невірні дані — `401`.

## GET /warehouses/{id}

```json
{ "warehouse_id": 1, "warehouse_name": "А-01", "warehouse_address": null, "total_warehouse_area": 1000.0 }
```

## GET / PUT /warehouses/{id}/map

Топологія складу з конструктора. **Одиниці — метри.** `coord_x`/`coord_y` — **центр** об'єкта.
`length` — розмір уздовж власної осі X об'єкта (до повороту), `width` — уздовж осі Y.
`rotation_angle` — градуси за годинниковою стрілкою.

PUT повністю замінює топологію: об'єкти з `*_id` оновлюються, без `*_id` створюються,
відсутні у запиті видаляються. Відповідь на PUT — збережена мапа з `*_id` нових об'єктів
(щоб наступне збереження не створювало дублікати).

```json
{
  "walls": [
    { "vertex_order": 1, "coord_x": 0, "coord_y": 0 },
    { "vertex_order": 2, "coord_x": 30, "coord_y": 0 },
    { "vertex_order": 3, "coord_x": 30, "coord_y": 20 },
    { "vertex_order": 4, "coord_x": 0, "coord_y": 20 }
  ],
  "racks": [
    { "rack_id": 7, "rack_code": "R-1", "coord_x": 8, "coord_y": 5, "length": 2.7, "width": 1.1,
      "rotation_angle": 0, "shelves_count": 3 }
  ],
  "obstacles": [
    { "obstacle_id": 2, "obstacle_name": "Колона", "obstacle_type": "column", "coord_x": 16, "coord_y": 11,
      "length": 2, "width": 2, "rotation_angle": 0, "max_height": null }
  ],
  "zones": [
    { "zone_id": 3, "zone_name": "Зона приймання", "zone_type": "inbound_dock", "coord_x": 25, "coord_y": 5,
      "length": 6, "width": 6, "rotation_angle": 0, "max_capacity_m3": null }
  ],
  "entry_points": [
    { "point_id": 1, "point_name": "Вхід", "point_type": "general_entry", "coord_x": 15, "coord_y": 20 }
  ]
}
```

- `walls` — вершини контуру приміщення (модель `WarehouseWalls`), полігон замикається автоматично.
- `obstacle_type`: `column | pillar | niche | restricted_zone | other`.
- `zone_type`: `inbound_dock | storage_area | outbound_dock`.
- `point_type`: `inbound | outbound | general_entry`.
- Порожній склад: усі масиви порожні (`200`, а не `404`).

**Що треба змінити на бекенді:**
1. `app/schemas.py` — `WarehouseMapUpdateSchema` зараз чекає `walls` як відрізки `{x1,y1,x2,y2}`
   і не має `obstacles` / `entry_points`. Потрібно привести до формату вище.
2. Модель `Zone` не має `length`, `width`, `rotation_angle` — без них зону не намалювати.
3. Моделі `WarehouseObstacles` бракує `rotation_angle`.
4. У `Rack.width/length` вказано `help_text="mm"`, а координати мапи — у метрах.
   Варто домовитися про одну одиницю для мапи (фронт працює в метрах).

## GET /warehouses/{id}/racks

```json
[ { "rack_id": 7, "rack_code": "R-1", "shelves_count": 3, "fill_percent": 68 } ]
```
`fill_percent` — 0…100, ціле. Стелаж зіставляється з мапою за `rack_code`.

## GET /warehouses/{id}/racks/{rack_code}

```json
{
  "rack_id": 7,
  "rack_code": "R-1",
  "zone_name": "Зона зберігання",
  "updated_at": "2026-10-23T09:42:00Z",
  "shelves": [
    { "shelf_id": 21, "shelf_code": "R-1-1", "product_name": "Цукор, 50 кг",
      "occupied": 8, "capacity": 10, "shelf_status": "occupied" }
  ]
}
```
`occupied` / `capacity` — у палетомісцях. `shelf_status`: `active | occupied | inactive`.
`zone_name` і `product_name` можуть бути `null`. Невідомий стелаж — `404` з `detail`.

## GET /warehouses/{id}/dashboard

```json
{
  "racks_count": 12,
  "zones_count": 3,
  "fill_percent": 68,
  "fill_change_week": 4,
  "on_shift": 5,
  "employees_total": 12,
  "free_area_m2": 320,
  "total_area_m2": 1000,
  "updated_at": "2026-10-23T09:00:00Z",
  "rack_fill": [ { "rack_id": 7, "rack_code": "R-1", "fill_percent": 68 } ],
  "recent_operations": [
    { "log_id": 101, "timestamp": "2026-10-23T09:42:00Z", "action": "Прийнято 40 коробок → R-3" }
  ]
}
```
`recent_operations` — останні ~6 записів `AuditLog`, новіші першими.

## GET /users?warehouse_id={id}

```json
[
  { "user_id": 1, "user_email": "i.petrenko@prostock.ua", "first_name": "Іван", "last_name": "Петренко",
    "role": "storekeeper", "status": "active", "position": "Водій навантажувача", "on_shift": true,
    "created_at": "2026-10-01T08:00:00Z" }
]
```
- `role`: `root | administrator | warehouse_manager | storekeeper`.
- `position` — посада для відображення; якщо `null`, фронт покаже назву ролі. У моделі `User` такого поля поки немає.
- `on_shift` — чи на зміні зараз. Обліку змін у моделях поки немає.

## POST /users

```json
// запит
{ "first_name": "Іван", "last_name": "Петренко", "user_email": "i.petrenko@prostock.ua",
  "password": "********", "role": "storekeeper", "warehouse_id": 1 }
// відповідь 201 — створений користувач у форматі як у GET /users
```
Зайнятий email — `409` з `detail`. За SRS (FR-1.4) пароль має бути тимчасовим і змінюватися при першому вході.
