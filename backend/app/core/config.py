from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Portal Automacoes API"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["development", "test", "production"] = "development"
    secret_key: str = Field(default="change-me", min_length=8)
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    postgres_server: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "portal"
    postgres_password: str = "portal"
    postgres_db: str = "portal_automacoes"

    redis_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    frontend_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    first_superuser_email: str = "admin@portal.local"
    first_superuser_password: str = "admin123"
    first_superuser_name: str = "Administrator"

    # ETA calculation settings
    eta_percentile: int = 75
    eta_window: int = 20
    worker_heartbeat_window_seconds: int = 60

    # Public URL of this backend, used to build package download links for the
    # Automation Agent when storage_backend="local".
    backend_public_url: str = "http://localhost:8000"

    # --- Package/artifact storage ---
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: str = "/data/packages"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_use_path_style: bool = True
    packages_bucket_name: str = "automation-packages"

    # --- Manual ZIP upload limits ---
    max_upload_size_mb: int = 200
    import_staging_ttl_seconds: int = 1800

    # --- GitHub App integration ---
    # Create the App at https://github.com/settings/apps/new (see
    # docs/github-app-setup.md for the exact steps and required permissions).
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_client_id: str | None = None
    github_app_client_secret: str | None = None
    github_app_private_key: str | None = None  # PEM contents (use \n for newlines in .env)
    github_app_webhook_secret: str | None = None
    github_api_base_url: str = "https://api.github.com"

    @property
    def github_app_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_private_key)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
