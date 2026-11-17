"""ThreatLens AI - Application configuration (environment-driven)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # -- Identity -------------------------------------------------------------
    app_name: str = "ThreatLens AI"
    app_version: str = "1.0.0"
    environment: str = "development"  # development | production

    # -- Networking -----------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    # Deliberate CORS policy: localhost dev origins + the sandbox preview.
    # In production, restrict to the deployed frontend origin.
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,"
        "http://127.0.0.1:5173,https://preview-zai-web.space-z.ai"
    )

    # -- Model artefacts --------------------------------------------------------
    artifacts_dir: Path = BACKEND_DIR / "artifacts"

    # -- Supabase Auth / Postgres ------------------------------------------------
    # The backend only needs the project URL and the PUBLISHABLE (anon) key:
    # every data query is executed with the caller's own verified access token
    # so Supabase Row Level Security enforces user isolation at the database.
    # No service-role / privileged key is used anywhere in this codebase.
    supabase_url: str = ""  # e.g. https://<project-ref>.supabase.co
    supabase_publishable_key: str = ""  # publishable/anon key - safe by design
    # Token verification strategy:
    #   auto     : JWKS signature verification if asymmetric keys are published,
    #              otherwise the Supabase Auth /user endpoint (secure fallback)
    #   jwks     : force JWKS signature verification (ES256/RS256)
    #   userinfo : always validate the token against Supabase Auth /user
    supabase_auth_mode: str = "auto"
    # Access-token audience allowlist (comma-separated). Supabase issues
    # access tokens with aud="authenticated"; the project ref is accepted too.
    supabase_jwt_audiences: str = "authenticated"
    supabase_jwt_leeway_seconds: int = 10

    # -- History / persistence ---------------------------------------------------
    # disabled  : nothing is stored
    # memory    : in-process only, cleared on restart (privacy-strict)
    # sqlite    : local SQLite file, capped, user-managed via the API (dev only)
    # supabase  : Supabase Postgres via the Data API - every query carries the
    #             caller's verified JWT so RLS policies enforce ownership
    history_mode: str = "sqlite"
    history_retention_limit: int = 500
    database_path: Path = BACKEND_DIR / "data" / "threatlens.db"

    # -- Input limits --------------------------------------------------------------
    max_url_length: int = 2048
    max_body_bytes: int = 16 * 1024

    # -- Rate limiting (in-process sliding window; single-instance only) ---------
    rate_limit_scan_per_minute: int = 30

    # -- Optional integrations (none required for the core scanner) -----------------
    # Reputation providers are NOT integrated in this prototype; the service
    # reports an honest "not integrated" status.
    reputation_providers: str = ""  # comma-separated; empty = none

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url.strip()) and bool(
            self.supabase_publishable_key.strip()
        )

    @property
    def supabase_url_clean(self) -> str:
        return self.supabase_url.strip().rstrip("/")

    @property
    def supabase_project_ref(self) -> str:
        """Project ref parsed from the Supabase URL host (first label)."""
        host = self.supabase_url_clean.replace("https://", "").replace("http://", "")
        return host.split(".")[0] if host else ""

    @property
    def supabase_jwt_issuer(self) -> str:
        return f"{self.supabase_url_clean}/auth/v1"

    @property
    def supabase_jwt_audience_list(self) -> list[str]:
        return [
            a.strip() for a in self.supabase_jwt_audiences.split(",") if a.strip()
        ] or ["authenticated"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Ensure data directory exists (DB lives here)
(BACKEND_DIR / "data").mkdir(parents=True, exist_ok=True)
