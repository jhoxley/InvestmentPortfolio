"""Unit tests for the Projection page's horizon-button date arithmetic (022).

`_years_after` is the forward-looking counterpart to
`src/components/date_range_controls._years_before` — mirrors its leap-day
handling test, adapted for "N years after" instead of "N years before".
"""

from __future__ import annotations

from datetime import date

from src.pages._projection_chart import _years_after


def test_years_after_one_year() -> None:
    assert _years_after(date(2026, 9, 22), 1) == date(2027, 9, 22)


def test_years_after_five_years() -> None:
    assert _years_after(date(2026, 9, 22), 5) == date(2031, 9, 22)


def test_years_after_ten_years() -> None:
    assert _years_after(date(2026, 9, 22), 10) == date(2036, 9, 22)


def test_years_after_twenty_years() -> None:
    assert _years_after(date(2026, 9, 22), 20) == date(2046, 9, 22)


def test_years_after_handles_leap_day_safely() -> None:
    # 2024-02-29 is a leap day; 2025 is not a leap year, so "+1Y" falls back
    # to 2025-02-28 rather than raising ValueError.
    assert _years_after(date(2024, 2, 29), 1) == date(2025, 2, 28)


def test_years_after_leap_day_to_another_leap_year_stays_exact() -> None:
    # 2024 -> 2028 is leap-to-leap, so the exact day is preserved.
    assert _years_after(date(2024, 2, 29), 4) == date(2028, 2, 29)
