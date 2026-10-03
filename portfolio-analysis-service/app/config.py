"""Application configuration loaded from config.yaml."""

import datetime as dt
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


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


class ExcludedReturn(BaseModel):
    """A configured (instrument, date) price to treat as missing for VaR purposes."""

    identifier: str = Field(description="Identifier whose return on `date` is excluded")
    date: dt.date = Field(description="Calendar date of the excluded price observation")


class VarQualitySettings(BaseModel):
    """Thresholds used to classify a VaR estimate's quality (ok/degraded/insufficient)."""

    ok_max_rescaled_pct: float = Field(
        default=5.0, description="Rescaled market-value share (%) at or below which quality is ok"
    )
    ok_max_proxied_pct: float = Field(
        default=25.0, description="Proxied market-value share (%) at or below which quality is ok"
    )
    insufficient_min_scenario_ratio: float = Field(
        default=0.8,
        description="Minimum scenario_count / lookback_days ratio; below this, quality is "
        "insufficient",
    )
    insufficient_max_rescaled_pct: float = Field(
        default=20.0,
        description="Rescaled market-value share (%) above which quality is insufficient",
    )


class VarSettings(BaseModel):
    """Configuration for the historical-simulation VaR calculation (feature 012).

    Defaults follow docs/proposals/value-at-risk.md sections 3 and 5.
    """

    methodology_version: str = "1.0.0"
    lookbacks: dict[str, int] = Field(
        default_factory=lambda: {"1y": 260, "2y": 520, "5y": 1300},
        description="Look-back code to business-day window length",
    )
    confidence_levels_bp: list[int] = Field(
        default_factory=lambda: [9500, 9750, 9900],
        description="Confidence levels in basis points of probability (9500 = 95%)",
    )
    min_observed_share_per_scenario: float = Field(
        default=0.5,
        description="Minimum share of risky market value that must have an observed return "
        "source for a scenario day to be included",
    )
    sparse_density_threshold: float = Field(
        default=0.8,
        description="Minimum observed-day density (since first_observed) below which an "
        "instrument is treated as sparse in a window",
    )
    outlier_abs_return: float = Field(
        default=0.25, description="Absolute return magnitude above which a warning is raised"
    )
    quality: VarQualitySettings = VarQualitySettings()
    excluded_returns: list[ExcludedReturn] = Field(default_factory=list)


class Settings(BaseModel):
    """Top-level application settings."""

    data: DataSettings = DataSettings()
    market_data_service: MarketDataServiceSettings = MarketDataServiceSettings()
    identifier_mapping: IdentifierMappingSettings = IdentifierMappingSettings()
    var: VarSettings = VarSettings()


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
