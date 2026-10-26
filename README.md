# ProStock

репозиторій для проєкту ProStock (АВПЗ)

## Запуск у Docker

Скопіюйте `.env.example` та перейменуйте у `.env`, задайте `SECRET_KEY` і запустіть:
```bash
docker compose up --build
```

Після запуску:

- веб-панель: http://localhost:5173
- API: http://localhost:8000

PostgreSQL зберігається у volume `postgres_data`. Для зупинки контейнерів:
```bash
docker compose down
```

Для зупинки з видаленням бд:
```bash
docker compose down -v
```