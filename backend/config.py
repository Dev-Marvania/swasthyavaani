"""
SwasthyaVaani — Application Configuration
Loads all settings from .env via Pydantic Settings.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config — every field maps to an env var."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Gnani API Platform (Required: Prisma v3.0 STT + Timbre v3.0 TTS) ──
    gnani_api_key: str = ""
    gnani_access_key: str = ""
    gnani_stt_ws_url: str = "wss://api.vachana.ai/stt/v3/stream"
    gnani_tts_ws_url: str = "wss://api.vachana.ai/api/v1/tts"

    # ── LLM Provider (Google Gemini) ──
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.1-flash-lite"

    @field_validator("llm_model", mode="before")
    @classmethod
    def normalize_model(cls, v: str) -> str:
        if not v:
            return "gemini-3.1-flash-lite"
        v_clean = v.strip().lower().replace(" ", "-")
        if "3.1" in v_clean:
            return "gemini-3.1-flash-lite"
        if "3.5" in v_clean:
            return "gemini-3.5-flash-lite"
        if "lite" in v_clean:
            return "gemini-3.1-flash-lite"
        return v_clean

    # ── DPDP Compliance ──
    encryption_key: str = ""  # 32-byte Fernet key — generate with Fernet.generate_key()
    sqlite_db_path: str = "swasthyavaani.db"

    # ── Runtime ──
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000


# Singleton — import this wherever you need config
settings = Settings()
