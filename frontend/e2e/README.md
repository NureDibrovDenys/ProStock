# E2E-перевірки веб-панелі

Сценарії Playwright (Python), які проходять реальний UI.

## Основний сценарій

`check_ui.py` — валідація входу, створення категорії й товару, редагування, видалення,
імпорт зі звітом про помилки, експорт CSV/Excel, RBAC для комірника, відновлення та
завершення сесії. Сценарій **самодостатній**: створює власні дані, тому працює навіть
на порожній базі.

```bash
# 1. Бекенд і фронтенд уже працюють
#    backend: uvicorn app.main:app --port 8000
#    frontend: npm run dev

# 2. Залежності
python3 -m pip install playwright
python3 -m playwright install chromium

# 3. Прогін (за замовчуванням http://127.0.0.1:5173)
python3 frontend/e2e/check_ui.py
# або
PROSTOCK_WEB_URL=http://127.0.0.1:5174 python3 frontend/e2e/check_ui.py
```

Очікуваний результат: `50 passed, 0 failed`.

## Авто-вихід за таймером

`check_autologout.py` перевіряє, що після втрати refresh-сесії застосунок сам
переходить на сторінку входу з повідомленням «Сесія завершилася». Потрібен бекенд
із коротким TTL access-токена (див. docstring файлу).

```bash
cd backend
DB_NAME=prostock ACCESS_TOKEN_EXPIRE_MINUTES=1 uvicorn app.main:app --port 8010

cd frontend
VITE_API_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5180

PROSTOCK_WEB_URL=http://127.0.0.1:5180 python3 frontend/e2e/check_autologout.py
```

Скрипти використовують стартові акаунти (`admin@prostock.com` / `Admin12345`,
`worker@prostock.com` / `Worker12345`), тому запускайте їх на dev-базі.
