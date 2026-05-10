from pathlib import Path

import yaml
from pydantic import BaseModel


class CacheSettings(BaseModel):
    directory: Path = Path("./cache")


class Settings(BaseModel):
    cache: CacheSettings = CacheSettings()


def load_settings(config_path: Path = Path("config.yaml")) -> Settings:
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return Settings.model_validate(data)
    return Settings()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
