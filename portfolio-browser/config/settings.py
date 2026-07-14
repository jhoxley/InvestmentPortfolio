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
