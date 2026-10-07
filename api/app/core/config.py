from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PROJECT_ROOT.parent
ENV_FILES = (REPOSITORY_ROOT / ".env", PROJECT_ROOT / ".env")

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Leeral API"
    environment: Environment = "development"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8000"
    cors_origins: list[str] = Field(default_factory=list)

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/leeral"
    database_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 60

    otp_length: int = 6
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_delivery: Literal["whatsapp", "console"] = "whatsapp"
    default_phone_region: str = "SN"

    storage_backend: Literal["r2", "local"] = "r2"
    local_storage_path: Path = PROJECT_ROOT / "var" / "storage"
    r2_account_id: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: SecretStr = SecretStr("")
    r2_secret_access_key: SecretStr = SecretStr("")
    r2_bucket: str = "leeral-files"
    signed_url_ttl_seconds: int = 3600

    meta_app_id: str = ""
    meta_app_secret: SecretStr = SecretStr("")
    whatsapp_access_token: SecretStr = SecretStr("")
    whatsapp_verify_token: SecretStr = SecretStr("")
    whatsapp_waba_id: str = ""
    whatsapp_default_phone_id: str = ""
    graph_api_version: str = "v25.0"
    graph_api_base_url: str = "https://graph.facebook.com"
    whatsapp_otp_template: str = "leeral_code"
    whatsapp_reminder_template: str = "leeral_rappel"
    whatsapp_template_language: str = "fr"

    payment_provider: Literal["simulated"] = "simulated"

    max_pages_per_document: int = 10
    max_image_bytes: int = 12 * 1024 * 1024
    max_pdf_bytes: int = 20 * 1024 * 1024
    max_docx_bytes: int = 10 * 1024 * 1024
    max_audio_bytes: int = 16 * 1024 * 1024
    max_question_chars: int = 1000

    guest_document_ttl_hours: int = 24
    guest_inactivity_days: int = 30
    subscription_reminder_days: int = 2
    practice_session_size: int = 8

    @property
    def r2_endpoint(self) -> str:
        if self.r2_endpoint_url:
            return self.r2_endpoint_url
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def graph_api_url(self) -> str:
        return f"{self.graph_api_base_url.rstrip('/')}/{self.graph_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
