from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    SECRET_KEY: str = ""
    DEBUG: bool = False

    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"

    # ── Авторизація ────────────────────────────────────────────────────────
    # Час життя access-токена (короткий, бо є refresh)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # Час життя refresh-токена (зберігається в httpOnly cookie)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "prostock_refresh"
    # Secure-cookie вмикається на HTTPS (у production обов'язково)
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    # Дозволені origin для прямого звертання до API (у dev — Vite)
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Обмеження на кількість спроб входу
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_WINDOW_SECONDS: int = 300

    # ── Імпорт товарів ─────────────────────────────────────────────────────
    IMPORT_MAX_FILE_MB: int = 5
    IMPORT_MAX_ROWS: int = 5000

    # ── Початкові дані ─────────────────────────────────────────────────────
    SEED_DEFAULT_USERS: bool = True
    ADMIN_EMAIL: str = "admin@prostock.com"
    ADMIN_PASSWORD: str = "Admin12345"
    MANAGER_EMAIL: str = "manager@prostock.com"
    MANAGER_PASSWORD: str = "Manager12345"
    WORKER_EMAIL: str = "worker@prostock.com"
    WORKER_PASSWORD: str = "Worker12345"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra="ignore"
    )

settings = Settings()
