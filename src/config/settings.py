"""Environment-driven settings (local `.env`, Lambda env vars, etc.)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "litigation-api"
    LOG_LEVEL: str = "INFO"

    # Aurora / PostgreSQL — used only when reachable; otherwise the API returns mocks.
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "litigation"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_SSL: str = "disable"
    DB_CONNECT_TIMEOUT_SECONDS: float = 2.0


settings = Settings()
