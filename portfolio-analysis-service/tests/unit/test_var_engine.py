"""Unit tests for the VaR engine's pure functions: rank, VaR/ES, scenario PnL, estimate()."""

from datetime import date
from fractions import Fraction

import numpy as np
import pytest

from app.config import VarSettings
from app.services.var.engine import (
    estimate,
    rank_k,
    scenario_pnl,
    var_es,
)
from app.services.var.exposures import Exposure, PositionExposure
from app.services.var.return_panel import ReturnPanel


class TestRankK:
    """rank_k() computes k = n - ceil(n*p) + 1 using exact integer arithmetic."""

    @pytest.mark.parametrize(
        ("n", "p_bp", "expected_k"),
        [
            (260, 9500, 14),
            (260, 9750, 7),
            (260, 9900, 3),
            (520, 9500, 27),
            (520, 9750, 14),
            (520, 9900, 6),
            (1300, 9500, 66),
            (1300, 9750, 33),
            (1300, 9900, 14),
        ],
    )
    def test_matches_reference_values(self, n: int, p_bp: int, expected_k: int) -> None:
        """rank_k reproduces the reference table in spec.md / research.md."""
        assert rank_k(n, p_bp) == expected_k

    @pytest.mark.parametrize("n", [1, 2, 5, 20, 260, 520, 1300, 2000])
    @pytest.mark.parametrize("p_bp", [9500, 9750, 9900])
    def test_k_always_in_range(self, n: int, p_bp: int) -> None:
        """K never falls below 1 or exceeds n, for any n >= 1."""
        k = rank_k(n, p_bp)
        assert 1 <= k <= n


class TestVarEs:
    """var_es() computes VaR as the k-th largest loss and ES as the exact tail mean."""

    def test_losses_1_to_520_matches_hand_computed_values(self) -> None:
        """Losses 1..520 give the spec's worked VaR and ES figures exactly."""
        losses = np.arange(1, 521, dtype=float)
        result_95 = var_es(losses, 9500)
        result_975 = var_es(losses, 9750)
        result_99 = var_es(losses, 9900)

        assert result_95.var == pytest.approx(494.0)
        assert result_975.var == pytest.approx(507.0)
        assert result_99.var == pytest.approx(515.0)

        assert result_95.es == pytest.approx(507.5)
        assert result_975.es == pytest.approx(514.0)
        # m = 520 * (1 - 0.99) = 5.2; top 5 losses (520..516) plus 0.2 * 515
        expected_es_99 = (520 + 519 + 518 + 517 + 516 + Fraction(1, 5) * 515) / Fraction(26, 5)
        assert result_99.es == pytest.approx(float(expected_es_99), rel=1e-12)

    def test_var_and_es_are_monotonic_in_confidence(self) -> None:
        """Higher confidence gives a larger-or-equal VaR and ES."""
        rng = np.random.default_rng(42)
        losses = rng.standard_t(4, size=600)
        r95, r975, r99 = var_es(losses, 9500), var_es(losses, 9750), var_es(losses, 9900)
        assert r95.var <= r975.var <= r99.var
        assert r95.es <= r975.es <= r99.es
        assert r95.es >= r95.var
        assert r975.es >= r975.var
        assert r99.es >= r99.var


class TestScenarioPnl:
    """scenario_pnl() applies a returns matrix to a holdings vector."""

    def test_mini_example_from_spec(self) -> None:
        """The spec's worked 5-scenario, 2-position example reproduces exactly."""
        values = np.array([60000.0, 30000.0])
        returns = np.array(
            [
                [-0.012, 0.004],
                [0.005, -0.020],
                [-0.031, -0.025],
                [0.008, 0.011],
                [-0.002, 0.003],
            ]
        )
        pnl = scenario_pnl(returns, values)
        np.testing.assert_allclose(pnl, [-600.0, -300.0, -2610.0, 810.0, -30.0], atol=1e-9)

    def test_cash_contributes_nothing(self) -> None:
        """A zero-return column (standing in for Cash) contributes 0 to every scenario."""
        values = np.array([60000.0, 10000.0])
        returns = np.array([[-0.01, 0.0], [0.02, 0.0]])
        pnl = scenario_pnl(returns, values)
        np.testing.assert_allclose(pnl, [-600.0, 1200.0], atol=1e-9)


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


def _panel(
    identifiers: tuple[str, ...], grid: list[date], returns: np.ndarray, observed: np.ndarray
) -> ReturnPanel:
    return ReturnPanel(
        grid=tuple(grid),
        identifiers=identifiers,
        returns=returns,
        observed=observed,
        first_observed=dict.fromkeys(identifiers, grid[0]),
    )


class TestEstimate:
    """estimate() computes one (date, look-back) VaR/ES estimate from an exposure + panel."""

    def test_low_information_scenario_days_excluded(self) -> None:
        """A scenario day where <50% of risky value was observed is dropped (n reduced)."""
        exposure = _exposure([("A", "A", 60000.0), ("B", "B", 40000.0)])
        grid = [date(2026, 3, d) for d in range(2, 7)]
        # Day index 2 (2026-03-04): only B (40%) observed -> excluded by the 50% rule.
        returns = np.array(
            [
                [0.01, 0.02],
                [-0.01, 0.01],
                [0.00, 0.03],
                [0.02, -0.01],
                [-0.02, 0.00],
            ]
        )
        observed = np.array(
            [
                [True, True],
                [True, True],
                [False, True],
                [True, True],
                [True, True],
            ]
        )
        panel = _panel(("A", "B"), grid, returns, observed)

        result = estimate(
            exposure,
            panel,
            as_of_row=4,
            lookback_days=5,
            confidences_bp=(9500,),
            settings=VarSettings(),
        )

        assert result.scenario_count == 4

    def test_rescale_fills_missing_position_with_weighted_mean(self) -> None:
        """A position with no return on a scenario day takes the value-weighted mean of the rest."""
        exposure = _exposure([("A", "A", 60000.0), ("C", "C", 20000.0), ("B", "B", 20000.0)])
        grid = [date(2026, 3, 2)]
        returns = np.array([[-0.01, 0.02, np.nan]])
        observed = np.array([[True, True, False]])
        panel = _panel(("A", "C", "B"), grid, returns, observed)

        result = estimate(
            exposure,
            panel,
            as_of_row=0,
            lookback_days=1,
            confidences_bp=(9500,),
            settings=VarSettings(min_observed_share_per_scenario=0.0),
        )

        # mean of A (-1%) and C (+2%) weighted by value (60000, 20000) = 0.25%
        # scenario pnl = 60000*-0.01 + 20000*0.02 + 20000*0.0025 = -600+400+50 = -250
        assert result.scenario_pnls[0] == pytest.approx(-250.0)

    def test_zero_risky_value_is_ok_with_zero_var(self) -> None:
        """An account holding only Cash gets VaR/ES 0 and quality ok."""
        exposure = _exposure([], cash=10000.0)
        grid = [date(2026, 3, 2)]
        panel = _panel((), grid, np.zeros((1, 0)), np.zeros((1, 0), dtype=bool))

        result = estimate(
            exposure,
            panel,
            as_of_row=0,
            lookback_days=1,
            confidences_bp=(9500, 9900),
            settings=VarSettings(),
        )

        assert result.quality == "ok"
        assert all(level.var_gbp == pytest.approx(0.0) for level in result.levels)
        assert all(level.es_gbp == pytest.approx(0.0) for level in result.levels)
        assert result.actual_mv_pct == pytest.approx(100.0)
