"""Runtime settings (host/port/debug), overridable via environment/.env.

Kept separate from `content.py`: these are operational/deployment concerns,
not human-edited content (project constitution, Principle IV).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8050
    debug: bool = False

    # Backing service URLs (market-data-web-service, portfolio-analysis-service).
    # Defaults match run_end_to_end.ps1's port assignments for local development.
    market_data_service_url: str = "http://127.0.0.1:8001"
    portfolio_analysis_service_url: str = "http://127.0.0.1:8000"

    # Timeout for outbound calls to portfolio_analysis_service_url. Larger
    # accounts (e.g. ~40+ positions) have been observed taking 5-6.6s to
    # compute a response even when the service succeeds (verified via
    # portfolio-analysis-api.log: status 200 responses at 5057-6597ms) — a
    # 5s timeout was intermittently firing on correct, merely-slightly-slow
    # responses, surfacing as a false "Could not load ... data" error with
    # nothing wrong (or logged) on the service side. 20s gives real margin
    # above the worst observed case, including when two widgets both fetch
    # concurrently on the same account/date change.
    request_timeout_seconds: float = 20.0
