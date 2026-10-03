"""Unit tests for VarSettings defaults, overrides, and identifier mapping proxy fields."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, load_settings
from app.models.market_data import IdentifierMappingEntry


class TestVarSettingsDefaults:
    """Default values of Settings().var match the methodology proposal."""

    def test_default_methodology_version(self) -> None:
        assert Settings().var.methodology_version == "1.0.0"

    def test_default_lookbacks(self) -> None:
        assert Settings().var.lookbacks == {"1y": 260, "2y": 520, "5y": 1300}

    def test_default_confidence_levels_bp(self) -> None:
        assert Settings().var.confidence_levels_bp == [9500, 9750, 9900]

    def test_default_min_observed_share_per_scenario(self) -> None:
        assert Settings().var.min_observed_share_per_scenario == pytest.approx(0.5)

    def test_default_sparse_density_threshold(self) -> None:
        assert Settings().var.sparse_density_threshold == pytest.approx(0.8)

    def test_default_outlier_abs_return(self) -> None:
        assert Settings().var.outlier_abs_return == pytest.approx(0.25)

    def test_default_quality_thresholds(self) -> None:
        quality = Settings().var.quality
        assert quality.ok_max_rescaled_pct == pytest.approx(5)
        assert quality.ok_max_proxied_pct == pytest.approx(25)
        assert quality.insufficient_min_scenario_ratio == pytest.approx(0.8)
        assert quality.insufficient_max_rescaled_pct == pytest.approx(20)

    def test_default_excluded_returns_empty(self) -> None:
        assert Settings().var.excluded_returns == []


class TestVarSettingsYamlOverride:
    """load_settings() applies a config.yaml var: section over the defaults."""

    def test_overrides_methodology_version_and_lookbacks(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """
var:
  methodology_version: "1.1.0"
  lookbacks: {"1y": 260, "3y": 780}
  confidence_levels_bp: [9900]
""",
            encoding="utf-8",
        )
        settings = load_settings(config_path=config)
        assert settings.var.methodology_version == "1.1.0"
        assert settings.var.lookbacks == {"1y": 260, "3y": 780}
        assert settings.var.confidence_levels_bp == [9900]

    def test_excluded_returns_parses_identifier_and_date(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text(
            """
var:
  excluded_returns:
    - identifier: "GB0031348658"
      date: "2026-02-10"
""",
            encoding="utf-8",
        )
        settings = load_settings(config_path=config)
        assert len(settings.var.excluded_returns) == 1
        excluded = settings.var.excluded_returns[0]
        assert excluded.identifier == "GB0031348658"
        assert str(excluded.date) == "2026-02-10"


class TestIdentifierMappingEntryVarFields:
    """IdentifierMappingEntry accepts the new optional VaR proxy fields."""

    def test_entry_without_var_fields_uses_defaults(self) -> None:
        entry = IdentifierMappingEntry(name="Equity A", ticker="EQA.L")
        assert entry.var_proxy is None
        assert entry.var_proxy_mode == "fill_gaps"
        assert entry.var_proxy_scale == pytest.approx(1.0)

    def test_entry_with_var_fields(self) -> None:
        entry = IdentifierMappingEntry(
            name="Scottish Widows Pension",
            isin="SWPENSION",
            var_proxy="GB00B08HD927",
            var_proxy_mode="always",
            var_proxy_scale=1.5,
        )
        assert entry.var_proxy == "GB00B08HD927"
        assert entry.var_proxy_mode == "always"
        assert entry.var_proxy_scale == pytest.approx(1.5)

    def test_var_proxy_scale_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            IdentifierMappingEntry(name="Equity A", ticker="EQA.L", var_proxy_scale=0)

    def test_var_proxy_mode_rejects_unknown_value(self) -> None:
        with pytest.raises(ValidationError):
            IdentifierMappingEntry(
                name="Equity A", ticker="EQA.L", var_proxy_mode="sometimes"  # type: ignore[arg-type]
            )
