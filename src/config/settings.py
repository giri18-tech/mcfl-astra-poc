"""Environment-driven settings (local `.env`, Lambda env vars, etc.)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "litigation-api"
    LOG_LEVEL: str = "INFO"

    # SQL Server — pymssql ships FreeTDS in its wheel; no ODBC driver required.
    # In Lambda these are set from SSM / Secrets Manager via the SAM template.
    # For local dev, create src/.env (see src/dev.env for a template).
    DB_HOST: str = "localhost"
    DB_PORT: int = 1433
    DB_NAME: str = "LitigationTracking_QA"
    DB_USER: str = "astra"
    # No default — must be supplied via env var or .env file.
    DB_PASSWORD: str
    DB_CONNECT_TIMEOUT_SECONDS: float = 5.0


settings = Settings()
