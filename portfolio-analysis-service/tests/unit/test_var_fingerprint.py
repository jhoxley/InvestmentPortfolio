"""Unit tests for config/holdings fingerprinting (incremental VaR recomputation)."""

from datetime import date

from app.config import VarSettings
from app.services.var.exposures import Exposure, PositionExposure, ProxyConfig
from app.services.var.fingerprint import config_fingerprint, row_fingerprint


def _exposure(positions: list[tuple[str, str, float]], cash: float = 0.0) -> Exposure:
    pos = tuple(
        PositionExposure(sub_account=sa, identifier=ident, market_value=mv)
        for sa, ident, mv in positions
    )
    risky = sum(p.market_value for p in pos)
    return Exposure(
        as_of=date(2026, 3, 2),
        positions=pos,
        cash_value=cash,
        risky_value=risky,
        total_value=risky + cash,
    )


class TestConfigFingerprint:
    """config_fingerprint() changes exactly when the methodology/config actually changes."""

    def test_same_settings_give_same_fingerprint(self) -> None:
        """Two equal VarSettings/proxy_configs give identical fingerprints."""
        a = config_fingerprint(VarSettings(), {})
        b = config_fingerprint(VarSettings(), {})
        assert a == b

    def test_methodology_version_change_changes_fingerprint(self) -> None:
        """Changing methodology_version changes the fingerprint."""
        a = config_fingerprint(VarSettings(methodology_version="1.0.0"), {})
        b = config_fingerprint(VarSettings(methodology_version="1.0.1"), {})
        assert a != b

    def test_lookback_change_changes_fingerprint(self) -> None:
        """Changing the lookbacks mapping changes the fingerprint."""
        a = config_fingerprint(VarSettings(lookbacks={"1y": 260}), {})
        b = config_fingerprint(VarSettings(lookbacks={"1y": 261}), {})
        assert a != b

    def test_quality_threshold_change_changes_fingerprint(self) -> None:
        """Changing a nested quality threshold changes the fingerprint."""
        from app.config import VarQualitySettings

        a = config_fingerprint(VarSettings(quality=VarQualitySettings(ok_max_rescaled_pct=5)), {})
        b = config_fingerprint(VarSettings(quality=VarQualitySettings(ok_max_rescaled_pct=6)), {})
        assert a != b

    def test_proxy_config_change_changes_fingerprint(self) -> None:
        """Adding/changing a proxy config changes the fingerprint."""
        a = config_fingerprint(VarSettings(), {})
        b = config_fingerprint(
            VarSettings(), {"X": ProxyConfig(proxy="Y", mode="always", scale=1.0)}
        )
        c = config_fingerprint(
            VarSettings(), {"X": ProxyConfig(proxy="Y", mode="always", scale=1.5)}
        )
        assert a != b
        assert b != c

    def test_proxy_config_order_does_not_matter(self) -> None:
        """Dict insertion order of proxy_configs does not affect the fingerprint."""
        configs_1 = {
            "A": ProxyConfig(proxy="PA", mode="fill_gaps", scale=1.0),
            "B": ProxyConfig(proxy="PB", mode="always", scale=2.0),
        }
        configs_2 = {
            "B": ProxyConfig(proxy="PB", mode="always", scale=2.0),
            "A": ProxyConfig(proxy="PA", mode="fill_gaps", scale=1.0),
        }
        assert config_fingerprint(VarSettings(), configs_1) == config_fingerprint(
            VarSettings(), configs_2
        )


class TestRowFingerprint:
    """row_fingerprint() changes exactly when a date's holdings (to the penny) change."""

    def test_same_exposure_gives_same_fingerprint(self) -> None:
        """Identical exposures give identical fingerprints."""
        cfg = config_fingerprint(VarSettings(), {})
        exp = _exposure([("A", "A", 1000.0)], cash=500.0)
        assert row_fingerprint(cfg, exp) == row_fingerprint(cfg, exp)

    def test_position_order_does_not_matter(self) -> None:
        """The order positions appear in does not affect the fingerprint."""
        cfg = config_fingerprint(VarSettings(), {})
        exp_1 = _exposure([("A", "A", 1000.0), ("B", "B", 2000.0)])
        exp_2 = _exposure([("B", "B", 2000.0), ("A", "A", 1000.0)])
        assert row_fingerprint(cfg, exp_1) == row_fingerprint(cfg, exp_2)

    def test_sub_pence_change_does_not_change_fingerprint(self) -> None:
        """A market-value change in the 3rd decimal place (rounded away) is a no-op."""
        cfg = config_fingerprint(VarSettings(), {})
        exp_1 = _exposure([("A", "A", 1000.001)])
        exp_2 = _exposure([("A", "A", 1000.004)])
        assert row_fingerprint(cfg, exp_1) == row_fingerprint(cfg, exp_2)

    def test_one_penny_change_changes_fingerprint(self) -> None:
        """A 1p market-value change changes the fingerprint."""
        cfg = config_fingerprint(VarSettings(), {})
        exp_1 = _exposure([("A", "A", 1000.00)])
        exp_2 = _exposure([("A", "A", 1000.01)])
        assert row_fingerprint(cfg, exp_1) != row_fingerprint(cfg, exp_2)

    def test_cash_change_changes_fingerprint(self) -> None:
        """A change in cash_value changes the fingerprint even with positions unchanged."""
        cfg = config_fingerprint(VarSettings(), {})
        exp_1 = _exposure([("A", "A", 1000.0)], cash=500.0)
        exp_2 = _exposure([("A", "A", 1000.0)], cash=600.0)
        assert row_fingerprint(cfg, exp_1) != row_fingerprint(cfg, exp_2)

    def test_different_config_fingerprint_changes_row_fingerprint(self) -> None:
        """The same exposure under a different config fingerprint hashes differently."""
        cfg_a = config_fingerprint(VarSettings(methodology_version="1.0.0"), {})
        cfg_b = config_fingerprint(VarSettings(methodology_version="2.0.0"), {})
        exp = _exposure([("A", "A", 1000.0)])
        assert row_fingerprint(cfg_a, exp) != row_fingerprint(cfg_b, exp)

    def test_fingerprint_is_a_hex_string(self) -> None:
        """The fingerprint is a sha256 hex digest (64 hex characters)."""
        cfg = config_fingerprint(VarSettings(), {})
        exp = _exposure([("A", "A", 1000.0)])
        fp = row_fingerprint(cfg, exp)
        assert len(fp) == 64
        int(fp, 16)  # raises ValueError if not valid hex
