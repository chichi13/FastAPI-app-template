from enum import Enum
from typing import Any, List

from pydantic import model_validator
from pydantic.networks import AnyHttpUrl
from pydantic_settings import BaseSettings

DEFAULT_DATABASE_USER = "app"
DEFAULT_DATABASE_PASSWORD = "password"
DEFAULT_DATABASE_URL = "127.0.0.1"
DEFAULT_DATABASE_NAME = "app"
DEFAULT_DATABASE_PORT = 5432


class AppEnvironment(str, Enum):
    PRODUCTION = "production"
    DEV = "development"
    TESTING = "testing"


class Config(BaseSettings):
    """
    Base configuration.
    """

    API_V1_STR: str = "/api/v1"

    APP_VERSION: str = "Unversioned API"
    APP_BASE_URL: str = "http://localhost:8000"
    ENV: AppEnvironment = AppEnvironment.PRODUCTION

    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    PROJECT_NAME: str | None = "FastAPI app template"

    DATABASE_USER: str = DEFAULT_DATABASE_USER
    DATABASE_PASSWORD: str = DEFAULT_DATABASE_PASSWORD
    DATABASE_URL: str = DEFAULT_DATABASE_URL
    DATABASE_NAME: str = DEFAULT_DATABASE_NAME
    DATABASE_PORT: int = DEFAULT_DATABASE_PORT
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    # Use SQLALCHEMY_DATABASE_URI to override all the other database settings
    SQLALCHEMY_DATABASE_URI: str | None = None

    REDIS_CONNECTION: bool = False
    REDIS_URL: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_SOCKET_TIMEOUT: int = 5

    SENTRY_ENABLED: bool | None = False
    SENTRY_DSN: str | None = None
    SENTRY_ENV: str | None = "dev"

    LOGGING_LEVEL: str = "INFO"
    SQL_VERBOSE_LOGGING: bool = False

    ALGORITHM: str = "HS384"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10_080

    EMAIL_TOKEN_EXPIRE_HOURS: int = 24
    EMAIL_SENDER: str = "fastapi@example.com"
    EMAIL_SENDER_NAME: str = "FastAPI app template"

    MAILJET_API_KEY: str | None = None
    MAILJET_API_SECRET: str | None = None

    USERS_OPEN_REGISTRATION: bool = True

    JWT_ACCESS_TOKEN_KEY: str
    JWT_REFRESH_TOKEN_KEY: str

    # SSO
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    @model_validator(mode="before")
    def build_test_database_url(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("ENV") == AppEnvironment.TESTING:
            values["SQLALCHEMY_DATABASE_URI"] = "sqlite+aiosqlite:///testing.db"
        else:
            values["SQLALCHEMY_DATABASE_URI"] = values.get(
                "SQLALCHEMY_DATABASE_URI"
            ) or "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
                values.get("DATABASE_USER", DEFAULT_DATABASE_USER),
                values.get("DATABASE_PASSWORD", DEFAULT_DATABASE_PASSWORD),
                values.get("DATABASE_URL", DEFAULT_DATABASE_URL),
                values.get("DATABASE_PORT", DEFAULT_DATABASE_PORT),
                values.get("DATABASE_NAME", DEFAULT_DATABASE_NAME),
            )
        return values

    def is_dev(self) -> bool:
        return self.ENV == AppEnvironment.DEV

    def is_prod(self) -> bool:
        return self.ENV == AppEnvironment.PRODUCTION


settings = Config(_env_file=".env", _env_file_encoding="utf-8")
