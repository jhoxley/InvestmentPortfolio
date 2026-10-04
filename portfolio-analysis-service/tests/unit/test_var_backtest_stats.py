"""Unit tests for the pure backtest statistics functions (app/services/var/backtest.py).

Values are checked against docs/proposals/value-at-risk.md section 4.3's formulas and
the spec's hand-worked scenarios, within 1e-9 relative tolerance for decimals and
exactly for integers/strings (SC-002).
"""

import math

import pytest

from app.services.var.backtest import (
    christoffersen_independence,
    conditional_coverage,
    kupiec_pof,
    rolling_exception_counts,
    traffic_light_zone,
    var_stability,
)


class TestKupiecPof:
    """kupiec_pof(n, x, alpha) -> (lr, p_value)."""

    def test_zero_observations_is_undefined(self) -> None:
        """N=0 returns (None, None)."""
        assert kupiec_pof(0, 0, 0.01) == (None, None)

    def test_mid_range_matches_hand_computation(self) -> None:
        """A mid-range (N, x) matches the exact Kupiec LR/p-value formula."""
        n, x, alpha = 250, 6, 0.01
        pihat = x / n
        expected_lr = -2 * ((n - x) * math.log(1 - alpha) + x * math.log(alpha)) + 2 * (
            (n - x) * math.log(1 - pihat) + x * math.log(pihat)
        )
        expected_p = math.erfc(math.sqrt(expected_lr / 2))

        lr, p = kupiec_pof(n, x, alpha)

        assert lr is not None and p is not None
        assert lr == pytest.approx(expected_lr, rel=1e-9)
        assert p == pytest.approx(expected_p, rel=1e-9)

    def test_zero_exceptions_uses_0ln0_convention(self) -> None:
        """x=0: the model's term (x * ln(pihat)) must not raise log(0); LR is still finite."""
        lr, p = kupiec_pof(250, 0, 0.01)
        assert lr is not None and p is not None
        assert math.isfinite(lr)
        assert 0.0 <= p <= 1.0

    def test_all_exceptions_uses_0ln0_convention(self) -> None:
        """x=N: the (N-x) terms must not raise log(0); LR is still finite."""
        lr, p = kupiec_pof(250, 250, 0.01)
        assert lr is not None and p is not None
        assert math.isfinite(lr)


class TestChristoffersenIndependence:
    """christoffersen_independence(dated_indicators) -> (lr, p_value)."""

    def test_fewer_than_two_observations_is_undefined(self) -> None:
        """Fewer than 2 observations returns (None, None)."""
        assert christoffersen_independence([(1, False)]) == (None, None)
        assert christoffersen_independence([]) == (None, None)

    def test_gap_breaks_the_transition_chain(self) -> None:
        """A gap (non-consecutive ordinal) must not be counted as a transition (FR-014)."""
        # Ordinals 1,2,3 are consecutive; 3->6 has a gap and must not count.
        with_gap = [(1, False), (2, False), (3, True), (6, True), (7, False)]
        without_gap = [(1, False), (2, False), (3, True), (4, True), (5, False)]

        lr_gap, _ = christoffersen_independence(with_gap)
        lr_no_gap, _ = christoffersen_independence(without_gap)

        # Both sequences have the same raw indicators but different adjacency -- the
        # gapped sequence must produce a different statistic (fewer counted transitions).
        assert lr_gap != lr_no_gap

    def test_single_transition_type_is_still_defined(self) -> None:
        """All-same indicators (e.g. no exceptions at all) still yields a finite LR."""
        seq = [(i, False) for i in range(10)]
        lr, p = christoffersen_independence(seq)
        assert lr is not None and p is not None
        assert math.isfinite(lr)


class TestConditionalCoverage:
    """conditional_coverage(lr_pof, lr_ind) -> (lr, p_value)."""

    def test_none_if_either_input_is_none(self) -> None:
        """Either input being None propagates to a (None, None) result."""
        assert conditional_coverage(None, 1.0) == (None, None)
        assert conditional_coverage(1.0, None) == (None, None)

    def test_sums_the_two_likelihood_ratios(self) -> None:
        """LR_cc is the sum of the two input likelihood ratios."""
        lr, p = conditional_coverage(1.5, 2.5)
        assert lr == pytest.approx(4.0)
        assert p == pytest.approx(math.exp(-4.0 / 2))


class TestTrafficLightZone:
    """traffic_light_zone(n, x, alpha) reproduces Basel's 0-4/5-9/10+ at N=250, 99%."""

    def test_zero_observations_is_undefined(self) -> None:
        """N=0 returns None."""
        assert traffic_light_zone(0, 0, 0.01) is None

    @pytest.mark.parametrize(
        ("x", "zone"),
        [(0, "green"), (4, "green"), (5, "yellow"), (9, "yellow"), (10, "red"), (11, "red")],
    )
    def test_basel_250_day_99pct_thresholds(self, x: int, zone: str) -> None:
        """Each exception count maps to the exact Basel zone at N=250, 99% (SC-003)."""
        assert traffic_light_zone(250, x, 0.01) == zone


class TestVarStability:
    """var_stability(values_with_holdings_changed) -> std dev of day-on-day log VaR change."""

    def test_fewer_than_two_qualifying_changes_is_undefined(self) -> None:
        """Fewer than 2 qualifying log-changes returns None."""
        assert var_stability([(100.0, False)]) is None
        assert var_stability([]) is None

    def test_excludes_holdings_changed_transitions(self) -> None:
        """A transition into a holdings-changed point contributes no log-change term."""
        # 100 -> 200 is a holdings change (excluded); 200 -> 100 is not.
        with_change = [(100.0, False), (200.0, True), (100.0, False)]
        # Without the excluded transition, only one log-change remains -> undefined (None).
        assert var_stability(with_change) is None

    def test_matches_hand_computed_std_dev(self) -> None:
        """A simple three-value series matches a manually computed sample std dev."""
        values = [(100.0, False), (110.0, False), (90.0, False)]
        log_changes = [math.log(110.0 / 100.0), math.log(90.0 / 110.0)]
        expected = (
            sum((lc - sum(log_changes) / len(log_changes)) ** 2 for lc in log_changes)
            / (len(log_changes) - 1)
        ) ** 0.5

        result = var_stability(values)

        assert result == pytest.approx(expected, rel=1e-9)


class TestRollingExceptionCounts:
    """rolling_exception_counts(indicators, window=250)."""

    def test_fewer_than_window_observations_returns_empty(self) -> None:
        """Fewer than `window` observations returns an empty list (never a partial window)."""
        assert rolling_exception_counts([False] * 249, window=250) == []

    def test_returns_one_point_per_date_from_the_window_th_observation_onward(self) -> None:
        """One rolling point per date from the window-th observation onward."""
        indicators = [False] * 300
        indicators[0] = True  # inside the first window only
        indicators[299] = True  # inside the last window only

        counts = rolling_exception_counts(indicators, window=250)

        assert len(counts) == 300 - 250 + 1
        assert counts[0] == 1  # window [0, 249] includes index 0
        assert counts[-1] == 1  # window [49, 299] includes index 299 but not index 0
