"""Application settings, loaded from environment variables (never hard-coded)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # Shared secret the dashboard sends in the X-API-Key header. Required outside development.
    api_key: str = Field(default="", description="Server-to-server API key")

    database_url: str = "sqlite:///./operations_intelligence.db"

    # Where operational records come from.
    # google_sheets: service account (recommended). google_sheets_link: sheet shared by link, no key.
    data_source: Literal["google_sheets", "google_sheets_link", "csv"] = "csv"
    csv_path: str = "../data/synthetic_daily_ops.csv"
    google_sheet_id: str = ""
    google_sheet_gid: str = "0"  # tab id, from "#gid=..." in the sheet URL (link mode only)
    google_sheet_range: str = "daily_ops!A1:L"
    # Either a path to the service-account JSON file, or the JSON itself (for hosts without a filesystem).
    google_service_account_file: str = ""
    google_service_account_json: str = ""

    # AI summary provider. "template" uses no model and is labelled as such everywhere.
    ai_provider: Literal["template", "openai_compatible"] = "template"
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_model: str = "llama-3.3-70b-versatile"
    ai_api_key: str = ""
    ai_timeout_seconds: float = 30.0

    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
