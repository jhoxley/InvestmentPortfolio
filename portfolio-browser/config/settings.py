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
