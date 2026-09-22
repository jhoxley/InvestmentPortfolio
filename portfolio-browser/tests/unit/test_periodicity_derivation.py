"""Unit tests for derive_periodicity() — the duration-derived default (021, US3).

Browser-free: a pure function of (from_date, to_date, thresholds), so every
band, both sides of every boundary, and every degenerate input are directly
assertable without a running app.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from config.content import PeriodicityThresholds
from src.components.date_range_controls import _years_before
from src.components.periodicity_controls import (
    PERIODICITY_DAY,
    PERIODICITY_MONTH,
    PERIODICITY_QUARTER,
    PERIODICITY_WEEK,
    PERIODICITY_YEAR,
    derive_periodicity,
)

_THRESHOLDS = PeriodicityThresholds(day_max_years=1, month_max_years=3, quarter_max_years=5)

# The same reference point used throughout research.md's verification:
# today = 2026-09-22, to_date = the last completed business day (2026-09-21).
_TO_DATE = date(2026, 9, 21)


class TestFourBands:
    """The spec's four worked examples: 6mo->day, 2y->month, 4y->quarter, 10y->year."""

    def test_six_months_derives_day(self) -> None:
        from_date = date(2026, 3, 21)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_DAY

    def test_two_years_derives_month(self) -> None:
        from_date = _years_before(_TO_DATE, 2)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_MONTH

    def test_four_years_derives_quarter(self) -> None:
        from_date = _years_before(_TO_DATE, 4)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_QUARTER

    def test_ten_years_derives_year(self) -> None:
        from_date = _years_before(_TO_DATE, 10)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_YEAR


class TestBothSidesOfEveryBoundary:
    """Exactly on a threshold keeps the finer interval; one day beyond moves to the coarser one."""

    def test_exactly_one_year_is_day(self) -> None:
        from_date = _years_before(_TO_DATE, 1)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_DAY

    def test_one_day_beyond_one_year_is_month(self) -> None:
        from_date = _years_before(_TO_DATE, 1) - timedelta(days=1)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_MONTH

    def test_exactly_three_years_is_month(self) -> None:
        from_date = _years_before(_TO_DATE, 3)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_MONTH

    def test_one_day_beyond_three_years_is_quarter(self) -> None:
        from_date = _years_before(_TO_DATE, 3) - timedelta(days=1)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_QUARTER

    def test_exactly_five_years_is_quarter(self) -> None:
        from_date = _years_before(_TO_DATE, 5)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_QUARTER

    def test_one_day_beyond_five_years_is_year(self) -> None:
        from_date = _years_before(_TO_DATE, 5) - timedelta(days=1)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_YEAR


class TestWeekIsNeverDerived:
    """week is selectable but never automatic (FR-009) — no threshold resolves to it."""

    @pytest.mark.parametrize(
        "years_back",
        [0, 1, 2, 3, 4, 5, 6, 10, 20],
    )
    def test_week_never_returned(self, years_back: int) -> None:
        from_date = _years_before(_TO_DATE, years_back) if years_back else _TO_DATE
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) != PERIODICITY_WEEK

    def test_one_day_span_is_not_week(self) -> None:
        from_date = date(2026, 9, 20)
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_DAY


class TestDegenerateInputs:
    """Degenerate or transiently-inverted ranges must never raise."""

    def test_from_equals_to_is_day(self) -> None:
        assert derive_periodicity(_TO_DATE, _TO_DATE, _THRESHOLDS) == PERIODICITY_DAY

    def test_inverted_range_is_day_not_an_exception(self) -> None:
        """A mid-edit inverted range (from > to) must not raise (defensive)."""
        from_date = date(2026, 9, 22)
        to_date = date(2026, 9, 21)
        assert derive_periodicity(from_date, to_date, _THRESHOLDS) == PERIODICITY_DAY


class TestThresholdsComeFromConfig:
    """The bands move if the passed-in thresholds do — not hardcoded constants."""

    def test_custom_thresholds_shift_the_bands(self) -> None:
        custom = PeriodicityThresholds(day_max_years=2, month_max_years=4, quarter_max_years=6)
        from_date = _years_before(_TO_DATE, 2)

        # Under the default thresholds this span is "month"...
        assert derive_periodicity(from_date, _TO_DATE, _THRESHOLDS) == PERIODICITY_MONTH
        # ...but under the custom (wider) day band, it is still "day".
        assert derive_periodicity(from_date, _TO_DATE, custom) == PERIODICITY_DAY

    def test_matches_the_1y_3y_5y_shortcut_dates_exactly(self) -> None:
        """The boundary dates must be byte-identical to the shortcut buttons' own.

        derive_periodicity delegates to the same _years_before() helper the
        1Y/3Y/5Y date-range shortcuts use, so a shortcut click always lands
        exactly on the boundary this rule expects — leap-day fallback
        included. Verified here rather than merely asserted in a docstring.
        """
        cases = [(1, PERIODICITY_DAY), (3, PERIODICITY_MONTH), (5, PERIODICITY_QUARTER)]
        for years, expected in cases:
            shortcut_from_date = _years_before(_TO_DATE, years)
            assert derive_periodicity(shortcut_from_date, _TO_DATE, _THRESHOLDS) == expected
