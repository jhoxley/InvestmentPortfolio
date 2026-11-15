"""Unit tests for build_scenario_matrix() and the contributions.py decomposition math."""

from datetime import date

import numpy as np
import pytest

from app.config import VarSettings
from app.services.var.contributions import (
    component_es,
    incremental_var,
    marginal_var,
    standalone_var,
    tail_weights,
)
from app.services.var.engine import (
    ScenarioMatrix,
    build_scenario_matrix,
    estimate,
    scenario_pnl,
    var_es,
)
from app.services.var.exposures import Exposure, PositionExposure
from app.services.var.return_panel import ReturnPanel


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
    identifiers: tuple[str, ...],
    grid: list[date],
    returns: np.ndarray,
    observed: np.ndarray,
    first_observed: dict[str, date | None] | None = None,
) -> ReturnPanel:
    return ReturnPanel(
        grid=tuple(grid),
        identifiers=identifiers,
        returns=returns,
        observed=observed,
        first_observed=first_observed or dict.fromkeys(identifiers, grid[0]),
    )


class TestBuildScenarioMatrixRegression:
    """build_scenario_matrix() reproduces exactly what estimate() already computed inline."""

    def test_matrix_reproduces_estimate_scenario_pnls(self) -> None:
        """scenario_pnl() on the matrix's included rows equals estimate()'s own scenario_pnls."""
        exposure = _exposure([("A", "A", 60000.0), ("C", "C", 20000.0), ("B", "B", 20000.0)])
        grid = [date(2026, 3, 2)]
        returns = np.array([[-0.01, 0.02, np.nan]])
        observed = np.array([[True, True, False]])
        panel = _panel(("A", "C", "B"), grid, returns, observed)
        settings = VarSettings(min_observed_share_per_scenario=0.0)

        result = estimate(
            exposure, panel, as_of_row=0, lookback_days=1, confidences_bp=(9500,), settings=settings
        )
        matrix = build_scenario_matrix(
            exposure, panel, as_of_row=0, lookback_days=1, settings=settings
        )

        assert isinstance(matrix, ScenarioMatrix)
        pnls = scenario_pnl(matrix.effective_returns[matrix.included], matrix.values)
        np.testing.assert_allclose(pnls, result.scenario_pnls, atol=1e-9)

    def test_provenance_matches_account_wide_coverage_percentages(self) -> None:
        """Market-value-weighted provenance over included rows reproduces the stored pcts."""
        exposure = _exposure(
            [("A", "actual", 70000.0), ("B", "proxied", 26000.0), ("C", "rescaled", 4000.0)]
        )
        grid = [date(2026, 3, 2)]
        panel = _panel(
            ("actual", "proxied", "rescaled", "P"),
            grid,
            np.array([[0.01, np.nan, np.nan, 0.02]]),
            np.array([[True, False, False, True]]),
        )
        from app.services.var.exposures import ProxyConfig

        configs = {"proxied": ProxyConfig(proxy="P", mode="fill_gaps", scale=1.0)}
        settings = VarSettings(min_observed_share_per_scenario=0.0)

        result = estimate(
            exposure,
            panel,
            as_of_row=0,
            lookback_days=1,
            confidences_bp=(9500,),
            settings=settings,
            proxy_configs=configs,
        )
        matrix = build_scenario_matrix(
            exposure, panel, as_of_row=0, lookback_days=1, settings=settings, proxy_configs=configs
        )

        assert matrix.provenance.shape == matrix.effective_returns.shape
        included_provenance = matrix.provenance[matrix.included]
        worst = included_provenance.max(axis=0)
        # codes: 0=actual, 1=proxy, 2=rescaled (engine._ACTUAL/_PROXY/_RESCALED)
        rescaled_value = float(matrix.values[worst == 2].sum())
        proxied_value = float(matrix.values[worst == 1].sum())
        risky_value = float(matrix.values.sum())
        rescaled_pct = 100.0 * rescaled_value / risky_value
        proxied_pct = 100.0 * proxied_value / risky_value

        assert rescaled_pct == pytest.approx(result.rescaled_mv_pct)
        assert proxied_pct == pytest.approx(result.proxied_mv_pct)


def _mini_example_columns() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The proposal's worked mini example (value-at-risk.md §3.4): A, B, and total PnL."""
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
    col_a = values[0] * returns[:, 0]
    col_b = values[1] * returns[:, 1]
    total = col_a + col_b
    np.testing.assert_allclose(total, [-600.0, -300.0, -2610.0, 810.0, -30.0], atol=1e-9)
    return col_a, col_b, total


class TestStandaloneVar:
    """standalone_var() is the quantile of a group's own PnL column in isolation."""

    def test_equals_var_es_on_the_negated_column(self) -> None:
        """standalone_var(col) matches var_es(-col, p_bp).var exactly."""
        col_a, _, _ = _mini_example_columns()
        assert standalone_var(col_a, 9500) == pytest.approx(var_es(-col_a, 9500).var)


class TestIncrementalVar:
    """incremental_var() is portfolio VaR minus portfolio-VaR-without-this-group."""

    def test_equals_total_var_minus_var_without_the_group(self) -> None:
        """incremental_var(total, group) equals the total/reduced VaR difference."""
        col_a, _col_b, total = _mini_example_columns()
        total_losses = -total
        reduced_losses = -(total - col_a)  # portfolio with A's column removed

        expected = var_es(total_losses, 9500).var - var_es(reduced_losses, 9500).var
        assert incremental_var(total_losses, col_a, 9500) == pytest.approx(expected)


class TestTailWeightsAndComponentEs:
    """component_es() uses the exact Acerbi-Tasche tail split and sums to total ES."""

    @pytest.mark.parametrize("p_bp", [9500, 9750, 9900])
    def test_components_sum_exactly_to_total_es(self, p_bp: int) -> None:
        """Summing component_es() over a full partition reproduces the portfolio's ES."""
        col_a, col_b, total = _mini_example_columns()
        total_losses = -total

        weights = tail_weights(total_losses, p_bp)
        es_a = component_es(col_a, weights)
        es_b = component_es(col_b, weights)
        total_es = var_es(total_losses, p_bp).es

        assert es_a + es_b == pytest.approx(total_es, abs=1e-9)

    def test_weights_reproduce_the_aggregate_es(self) -> None:
        """Dotting tail_weights() with the portfolio's own losses reproduces its ES."""
        _col_a, _col_b, total = _mini_example_columns()
        total_losses = -total
        weights = tail_weights(total_losses, 9900)

        reproduced_es = float(np.dot(weights, total_losses))
        assert reproduced_es == pytest.approx(var_es(total_losses, 9900).es)


class TestMarginalVar:
    """marginal_var() is component ES divided by market value, never NaN for zero risk."""

    def test_equals_component_over_market_value(self) -> None:
        """marginal_var(component, market_value) is simple division when value > 0."""
        assert marginal_var(1000.0, 50000.0) == pytest.approx(0.02)

    def test_zero_component_gives_zero_regardless_of_market_value(self) -> None:
        """A Cash-like group (zero component ES) never divides into NaN or an error."""
        assert marginal_var(0.0, 10000.0) == pytest.approx(0.0)
