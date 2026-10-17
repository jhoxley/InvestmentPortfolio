"""Unit tests for building business-day return grids from observed-only price history."""

from datetime import date

import numpy as np
import pytest

from app.config import ExcludedReturn
from app.models.market_data import ObservedPriceHistory, PriceHistoryPoint
from app.services.var.return_panel import apply_exclusions, build_return_panel, find_outliers


def _history(points: list[tuple[date, float]]) -> ObservedPriceHistory:
    prices = [PriceHistoryPoint(date=d, close=c) for d, c in points]
    return ObservedPriceHistory(
        points=prices,
        first_observed_date=prices[0].date if prices else None,
        last_observed_date=prices[-1].date if prices else None,
    )


class TestBuildReturnPanel:
    """build_return_panel() aligns observed prices onto a Mon-Fri business-day grid."""

    def test_grid_covers_exactly_the_requested_range(self) -> None:
        """The panel's grid is exactly the Mon-Fri business days in [grid_start, grid_end]."""
        # 2026-03-02 is a Monday; 2026-03-06 is the following Friday.
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 6),
        )
        assert list(panel.grid) == [
            date(2026, 3, 2),
            date(2026, 3, 3),
            date(2026, 3, 4),
            date(2026, 3, 5),
            date(2026, 3, 6),
        ]

    def test_return_uses_previous_observed_price(self) -> None:
        """A day's return is its price over the previous OBSERVED price, minus 1."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 4), 102.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 4),
        )
        col = panel.identifiers.index("EQA.L")
        # 2026-03-02: first observation -> NaN. 2026-03-03: no observation -> 0.0 (observed=False).
        # 2026-03-04: observed, return vs the previous OBSERVED price (03-02) = 102/100 - 1.
        row_idx = {d: i for i, d in enumerate(panel.grid)}
        assert np.isnan(panel.returns[row_idx[date(2026, 3, 2)], col])
        assert panel.returns[row_idx[date(2026, 3, 3)], col] == pytest.approx(0.0)
        assert not panel.observed[row_idx[date(2026, 3, 3)], col]
        assert panel.returns[row_idx[date(2026, 3, 4)], col] == pytest.approx(0.02)
        assert panel.observed[row_idx[date(2026, 3, 4)], col]

    def test_first_observed_day_return_is_nan(self) -> None:
        """The instrument's first observed day has no prior observation, so its return is NaN."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 4), 100.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 4),
        )
        col = panel.identifiers.index("EQA.L")
        row_idx = {d: i for i, d in enumerate(panel.grid)}
        assert np.isnan(panel.returns[row_idx[date(2026, 3, 2)], col])
        assert np.isnan(panel.returns[row_idx[date(2026, 3, 3)], col])
        assert np.isnan(panel.returns[row_idx[date(2026, 3, 4)], col])
        assert not panel.observed[row_idx[date(2026, 3, 4)], col]

    def test_return_spans_a_holiday_gap_correctly(self) -> None:
        """A multi-day gap between observations gives one return spanning both days."""
        panel = build_return_panel(
            {
                "EQA.L": _history(
                    [
                        (date(2026, 3, 2), 100.0),
                        (date(2026, 3, 3), 101.0),
                        # 2026-03-04 skipped (holiday)
                        (date(2026, 3, 5), 103.0),
                    ]
                )
            },
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 5),
        )
        col = panel.identifiers.index("EQA.L")
        row_idx = {d: i for i, d in enumerate(panel.grid)}
        assert panel.returns[row_idx[date(2026, 3, 5)], col] == pytest.approx(103.0 / 101.0 - 1.0)
        assert panel.observed[row_idx[date(2026, 3, 5)], col]

    def test_unobserved_day_within_history_is_zero_and_unobserved(self) -> None:
        """A grid day with no observation, inside the instrument's known history, is 0.0."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 6), 105.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 6),
        )
        col = panel.identifiers.index("EQA.L")
        row_idx = {d: i for i, d in enumerate(panel.grid)}
        for d in (date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5)):
            assert panel.returns[row_idx[d], col] == pytest.approx(0.0)
            assert not panel.observed[row_idx[d], col]

    def test_first_observed_recorded_per_identifier(self) -> None:
        """first_observed carries each identifier's known first-observed date."""
        panel = build_return_panel(
            {
                "EQA.L": _history([(date(2020, 1, 2), 50.0), (date(2026, 3, 2), 100.0)]),
                "EQB.L": ObservedPriceHistory(
                    points=[], first_observed_date=None, last_observed_date=None
                ),
            },
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 2),
        )
        assert panel.first_observed["EQA.L"] == date(2020, 1, 2)
        assert panel.first_observed["EQB.L"] is None

    def test_multiple_identifiers_are_independent_columns(self) -> None:
        """Each identifier gets its own column, unaffected by the others' observations."""
        panel = build_return_panel(
            {
                "EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 110.0)]),
                "EQB.L": _history([(date(2026, 3, 2), 50.0), (date(2026, 3, 3), 49.0)]),
            },
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        row_idx = {d: i for i, d in enumerate(panel.grid)}
        col_a = panel.identifiers.index("EQA.L")
        col_b = panel.identifiers.index("EQB.L")
        assert panel.returns[row_idx[date(2026, 3, 3)], col_a] == pytest.approx(0.1)
        assert panel.returns[row_idx[date(2026, 3, 3)], col_b] == pytest.approx(-0.02)


class TestFindOutliers:
    """find_outliers() lists observed returns exceeding a magnitude threshold."""

    def test_finds_return_above_threshold(self) -> None:
        """A return of +40% is found at threshold 0.25."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 140.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        outliers = find_outliers(panel, threshold=0.25)
        assert len(outliers) == 1
        assert outliers[0].identifier == "EQA.L"
        assert outliers[0].date == date(2026, 3, 3)
        assert outliers[0].value == pytest.approx(0.4)

    def test_return_below_threshold_not_found(self) -> None:
        """A return of +10% is not found at threshold 0.25."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 110.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        assert find_outliers(panel, threshold=0.25) == []

    def test_return_exactly_at_threshold_not_found(self) -> None:
        """A return of exactly +25% is not found (strictly greater than, per FR-028)."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 125.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        assert find_outliers(panel, threshold=0.25) == []

    def test_unobserved_days_never_count_as_outliers(self) -> None:
        """NaN (pre-inception) and zero-filled gap days are never reported as outliers."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 4), 100.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 4),
        )
        assert find_outliers(panel, threshold=0.25) == []


class TestApplyExclusions:
    """apply_exclusions() blanks configured bad prices and warns about each match."""

    def test_excluded_cell_becomes_nan_and_unobserved(self) -> None:
        """An excluded (identifier, date) cell is set to NaN with observed False."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 140.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        new_panel, _warnings = apply_exclusions(
            panel, [ExcludedReturn(identifier="EQA.L", date=date(2026, 3, 3))]
        )
        row = new_panel.grid.index(date(2026, 3, 3))
        col = new_panel.identifiers.index("EQA.L")
        assert np.isnan(new_panel.returns[row, col])
        assert not new_panel.observed[row, col]

    def test_excluded_cell_produces_a_warning(self) -> None:
        """A matched exclusion produces one excluded_price warning."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 140.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        _new_panel, warnings = apply_exclusions(
            panel, [ExcludedReturn(identifier="EQA.L", date=date(2026, 3, 3))]
        )
        assert len(warnings) == 1
        assert warnings[0].kind == "excluded_price"
        assert warnings[0].identifier == "EQA.L"
        assert warnings[0].date == date(2026, 3, 3)

    def test_non_matching_exclusion_produces_no_warning_and_no_change(self) -> None:
        """An exclusion for an identifier/date not in the panel is a no-op."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 140.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        new_panel, warnings = apply_exclusions(
            panel, [ExcludedReturn(identifier="UNKNOWN", date=date(2026, 3, 3))]
        )
        assert warnings == []
        np.testing.assert_array_equal(new_panel.returns, panel.returns)

    def test_no_exclusions_leaves_panel_unchanged(self) -> None:
        """An empty exclusion list returns an equivalent panel with no warnings."""
        panel = build_return_panel(
            {"EQA.L": _history([(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 140.0)])},
            grid_start=date(2026, 3, 2),
            grid_end=date(2026, 3, 3),
        )
        new_panel, warnings = apply_exclusions(panel, [])
        assert warnings == []
        np.testing.assert_array_equal(new_panel.returns, panel.returns)
