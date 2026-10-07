from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str

    # Storage
    STORAGE_PATH: str

    # Security
    SECRET_KEY: str

    # Application
    ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "info"
    MAX_RECIPIENTS_PER_JOB: int = 5000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
