from pathlib import Path
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    SECRET_KEY: SecretStr = SecretStr("")
    DEBUG: bool = False

    # DB
    DB_NAME: str = "prostock_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: SecretStr = SecretStr("")
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"

    # Authorization
    # Access token lifetime (short, since there is a refresh token)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # Refresh token lifetime (stored in an HttpOnly cookie)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "prostock_refresh"
    
    # Automatically set Secure=True in production (when DEBUG=False)
    @property
    def COOKIE_SECURE(self) -> bool:
        return not self.DEBUG
    
    # noinspection SpellCheckingInspection
    COOKIE_SAMESITE: str = "lax"
    # Allowed origins for direct API access (Vite in dev)
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Restrictions on the number of login attempts
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_WINDOW_SECONDS: int = 300

    # Restrictions on the products import
    IMPORT_MAX_FILE_MB: int = 5
    IMPORT_MAX_ROWS: int = 5000

    # Initial data (only for dev/seed)
    SEED_DEFAULT_USERS: bool = True
    
    ADMIN_EMAIL: str = "admin@prostock.com"
    ADMIN_PASSWORD: SecretStr = SecretStr("Admin12345")
    
    MANAGER_EMAIL: str = "manager@prostock.com"
    MANAGER_PASSWORD: SecretStr = SecretStr("Manager12345")
    
    WORKER_EMAIL: str = "worker@prostock.com"
    WORKER_PASSWORD: SecretStr = SecretStr("Worker12345")

    @model_validator(mode="after")
    def pyvalidate_production_settings(self) -> "Settings":
        if not self.DEBUG:
            if not self.SECRET_KEY.get_secret_value():
                raise ValueError("SECRET_KEY is required in production (DEBUG=False")
            if not self.DB_PASSWORD.get_secret_value():
                raise ValueError("DB_PASSWORD is required in production (DEBUG=False")
        return self
    
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD.get_secret_value()}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra="ignore"
    )

settings = Settings()
