# E2E-перевірка веб-панелі

Наскрізний сценарій Playwright (Python), який проходить реальний UI:
валідація входу, створення/редагування/видалення товару, імпорт зі звітом про
помилки, експорт CSV/Excel, RBAC для комірника, відновлення та завершення сесії.

## Запуск

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

Скрипт використовує стартові акаунти (`admin@prostock.com` / `Admin12345`,
`worker@prostock.com` / `Worker12345`), тому запускайте його на dev-базі.
