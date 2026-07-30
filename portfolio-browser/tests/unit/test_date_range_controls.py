"""Unit tests for the shared date-range/shortcut helpers in
src/components/date_range_controls.py (used by both Overview and Positions;
specs/018-positions-page/research.md #1).

No Dash app / browser required — these are plain functions taking/returning
dates and account summaries. Relocated verbatim from
tests/unit/test_overview_chart_shaping.py (behavior unchanged).
"""

from __future__ import annotations

from datetime import date

from src.components.date_range_controls import (
    SHORTCUT_1Y,
    SHORTCUT_3Y,
    SHORTCUT_5Y,
    SHORTCUT_ALL,
    SHORTCUT_YTD,
    _earliest_from_date,
    _last_business_day,
    _shortcut_from_date,
)
from src.models.portfolio_analysis import AccountResourceRange, AccountSummary


def test_last_business_day_from_monday_is_previous_friday() -> None:
    # 2024-01-08 is a Monday; 2024-01-05 is the preceding Friday.
    assert _last_business_day(date(2024, 1, 8)) == date(2024, 1, 5)


def test_last_business_day_from_tuesday_is_monday() -> None:
    assert _last_business_day(date(2024, 1, 9)) == date(2024, 1, 8)


def test_last_business_day_from_saturday_is_friday() -> None:
    assert _last_business_day(date(2024, 1, 6)) == date(2024, 1, 5)


def test_last_business_day_from_sunday_is_friday() -> None:
    assert _last_business_day(date(2024, 1, 7)) == date(2024, 1, 5)


def test_earliest_from_date_uses_min_of_both_ranges() -> None:
    account = AccountSummary(
        account_name="HL-SIPP",
        capital_ledger=AccountResourceRange(
            from_date=date(2016, 4, 20), to_date=date(2026, 6, 1)
        ),
        position_ladder=AccountResourceRange(
            from_date=date(2015, 1, 1), to_date=date(2026, 7, 8)
        ),
    )
    assert _earliest_from_date(account) == date(2015, 1, 1)


def test_earliest_from_date_with_only_capital_ledger() -> None:
    account = AccountSummary(
        account_name="capital-only-portfolio",
        capital_ledger=AccountResourceRange(
            from_date=date(2020, 1, 2), to_date=date(2020, 6, 1)
        ),
        position_ladder=None,
    )
    assert _earliest_from_date(account) == date(2020, 1, 2)


def test_earliest_from_date_with_only_position_ladder() -> None:
    account = AccountSummary(
        account_name="ladder-only-portfolio",
        capital_ledger=None,
        position_ladder=AccountResourceRange(
            from_date=date(2019, 3, 4), to_date=date(2020, 6, 1)
        ),
    )
    assert _earliest_from_date(account) == date(2019, 3, 4)


_LONG_HISTORY_ACCOUNT = AccountSummary(
    account_name="HL-SIPP",
    capital_ledger=AccountResourceRange(from_date=date(2010, 1, 1), to_date=date(2026, 6, 1)),
    position_ladder=AccountResourceRange(from_date=date(2010, 1, 1), to_date=date(2026, 7, 8)),
)

_SHORT_HISTORY_ACCOUNT = AccountSummary(
    account_name="new-portfolio",
    capital_ledger=AccountResourceRange(from_date=date(2025, 1, 1), to_date=date(2026, 6, 1)),
    position_ladder=None,
)


def test_shortcut_ytd_is_first_of_january_current_year() -> None:
    today = date(2026, 7, 16)
    assert _shortcut_from_date(SHORTCUT_YTD, _LONG_HISTORY_ACCOUNT, today) == date(2026, 1, 1)


def test_shortcut_1y_is_exact_calendar_offset() -> None:
    today = date(2026, 3, 15)
    assert _shortcut_from_date(SHORTCUT_1Y, _LONG_HISTORY_ACCOUNT, today) == date(2025, 3, 15)


def test_shortcut_3y_is_exact_calendar_offset() -> None:
    today = date(2026, 3, 15)
    assert _shortcut_from_date(SHORTCUT_3Y, _LONG_HISTORY_ACCOUNT, today) == date(2023, 3, 15)


def test_shortcut_5y_is_exact_calendar_offset() -> None:
    today = date(2026, 3, 15)
    assert _shortcut_from_date(SHORTCUT_5Y, _LONG_HISTORY_ACCOUNT, today) == date(2021, 3, 15)


def test_shortcut_1y_handles_leap_day_safely() -> None:
    # 2024-02-29 is a leap day; 2023 is not a leap year, so "1Y" falls back
    # to 28 Feb rather than raising ValueError.
    today = date(2024, 2, 29)
    assert _shortcut_from_date(SHORTCUT_1Y, _LONG_HISTORY_ACCOUNT, today) == date(2023, 2, 28)


def test_shortcut_all_is_the_accounts_earliest_from_date() -> None:
    today = date(2026, 7, 16)
    assert _shortcut_from_date(
        SHORTCUT_ALL, _LONG_HISTORY_ACCOUNT, today
    ) == _earliest_from_date(_LONG_HISTORY_ACCOUNT)


def test_shortcut_5y_clamps_to_accounts_earliest_from_date() -> None:
    # _SHORT_HISTORY_ACCOUNT only goes back to 2025-01-01 — far less than 5
    # years before "today" — so the computed date MUST be raised to the
    # account's own earliest recorded date (FR-008), not requested as-is.
    today = date(2026, 7, 16)
    assert _shortcut_from_date(SHORTCUT_5Y, _SHORT_HISTORY_ACCOUNT, today) == date(2025, 1, 1)


def test_shortcut_ytd_clamps_to_accounts_earliest_from_date() -> None:
    # An account that only started in June of this year has no January data.
    today = date(2026, 7, 16)
    mid_year_account = AccountSummary(
        account_name="mid-year-portfolio",
        capital_ledger=AccountResourceRange(
            from_date=date(2026, 6, 1), to_date=date(2026, 7, 1)
        ),
        position_ladder=None,
    )
    assert _shortcut_from_date(SHORTCUT_YTD, mid_year_account, today) == date(2026, 6, 1)
