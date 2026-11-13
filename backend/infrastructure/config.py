from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
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

    postgres_server: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "portal"
    postgres_password: str = "portal"
    postgres_db: str = "portal_automacoes"

    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/1"

    frontend_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    first_superuser_email: str = "admin@portal.local"
    first_superuser_password: str = "admin123"
    first_superuser_name: str = "Administrator"

    eta_percentile: int = 75
    eta_window: int = 20
    worker_heartbeat_window_seconds: int = 60

    agent_gateway_max_message_bytes: int = 64 * 1024
    agent_gateway_max_messages_per_second: int = 20
    agent_gateway_max_heartbeat_payload_bytes: int = 24 * 1024
    agent_gateway_max_capabilities_per_message: int = 200
    agent_gateway_max_attribute_depth: int = 6
    agent_gateway_max_pending_commands_per_agent: int = 50
    agent_gateway_handshake_timeout_seconds: int = 15
    agent_gateway_idle_timeout_seconds: int = 120

    backend_public_url: str = "http://localhost:8000"

    # E-mail pelo Microsoft Graph (Fase 6; centralizado em 13/11/2026). O segredo só vem do .env.
    # Aceita os nomes do Biason Comunica (ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET).
    # NOTIFICACOES_EMAIL_LIGADO: true/false força; sem a variável, liga sozinho quando os quatro
    # dados (tenant, aplicativo, segredo e remetente) estão no .env.
    notificacoes_email_ligado: bool | None = None
    graph_tenant_id: str = Field(default="", validation_alias=AliasChoices("graph_tenant_id", "entra_tenant_id"))
    graph_client_id: str = Field(default="", validation_alias=AliasChoices("graph_client_id", "entra_client_id"))
    graph_client_secret: SecretStr = Field(default=SecretStr(""),
                                           validation_alias=AliasChoices("graph_client_secret", "entra_client_secret"))
    graph_remetente: str = ""

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: str = "data/packages"
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_use_path_style: bool = True
    packages_bucket_name: str = "automation-packages"

    max_upload_size_mb: int = 200
    import_staging_ttl_seconds: int = 1800

    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_client_id: str | None = None
    github_app_client_secret: str | None = None
    github_app_private_key: str | None = None
    github_app_webhook_secret: str | None = None
    github_api_base_url: str = "https://api.github.com"

    governance_local_encryption_key: str | None = None
    production_secret_key_min_length: int = 32

    @model_validator(mode="after")
    def _validate_production_security(self) -> "Settings":
        if self.environment == "production":
            if self.secret_key == "change-me" or len(self.secret_key) < self.production_secret_key_min_length:
                raise ValueError("SECRET_KEY must be configured with a strong value in production.")
            if "*" in self.origins_list:
                raise ValueError("ALLOWED_ORIGINS cannot contain '*' in production.")
            if not self.governance_local_encryption_key:
                raise ValueError("GOVERNANCE_LOCAL_ENCRYPTION_KEY is required in production.")
        return self

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
