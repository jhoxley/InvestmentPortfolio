"""Application configuration loaded from config.yaml."""

from pathlib import Path

import yaml
from pydantic import BaseModel


class DataSettings(BaseModel):
    """Settings for the local data store directory."""

    directory: Path = Path("./data")


class MarketDataServiceSettings(BaseModel):
    """Settings for locating the market-data-web-service instance."""

    base_url: str = "http://127.0.0.1:8001"
    timeout_seconds: float = 30.0


class IdentifierMappingSettings(BaseModel):
    """Settings for locating the sub-account-to-identifier mapping file."""

    path: Path | None = None


class Settings(BaseModel):
    """Top-level application settings."""

    data: DataSettings = DataSettings()
    market_data_service: MarketDataServiceSettings = MarketDataServiceSettings()
    identifier_mapping: IdentifierMappingSettings = IdentifierMappingSettings()


def load_settings(config_path: Path = Path("config.yaml")) -> Settings:
    """Load settings from a YAML config file, falling back to defaults.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Populated Settings instance.
    """
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return Settings.model_validate(data)
    return Settings()


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton Settings instance, loading on first call.

    Returns:
        Application settings.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
