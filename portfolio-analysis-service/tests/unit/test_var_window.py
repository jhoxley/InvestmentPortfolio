"""Unit tests for resolve_window() -- date-window resolution without reading the ladder."""

from dataclasses import dataclass
from datetime import date

import pytest

from app.exceptions import (
    AccountNotFoundError,
    FutureEndDateError,
    InvalidDateRangeError,
    MissingRequiredSourceError,
)
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.var.var_window import resolve_window


@dataclass
class _FakeSourceMeta:
    from_date: date
    to_date: date


@dataclass
class _FakeSummary:
    capital_ledger: object | None
    position_ladder: _FakeSourceMeta | None


class _FakeAccountsService:
    """Stands in for AccountsService.get_summary() without touching the filesystem."""

    def __init__(self, summary: _FakeSummary) -> None:
        self._summary = summary

    def get_summary(self, account_name: str) -> _FakeSummary:
        return self._summary


def _summary_with_ladder(from_date: date, to_date: date) -> _FakeSummary:
    return _FakeSummary(
        capital_ledger=_FakeSourceMeta(from_date, to_date),
        position_ladder=_FakeSourceMeta(from_date, to_date),
    )


class TestResolveWindow:
    """resolve_window() validates and resolves exactly like DailyReturnSeriesLoader.load()."""

    def test_never_reads_the_full_ladder(self) -> None:
        """resolve_window() takes no LadderRepository at all -- it cannot read the full ladder.

        This is a regression guard: SC-004's 2-second budget depends on this function
        never acquiring a LadderRepository (and so never calling read_full_df()).
        """
        import inspect

        params = inspect.signature(resolve_window).parameters
        assert "ladder_repo" not in params

        summary = _summary_with_ladder(date(2026, 1, 2), date(2026, 3, 2))
        resolution = resolve_window(
            accounts_service=_FakeAccountsService(summary),
            date_resolver=TimeseriesDateResolver(),
            account_name="acct",
            start=None,
            end=date(2026, 3, 2),
            today=date(2026, 3, 2),
            attribute_label="var-series",
        )
        assert resolution.resolved_end == date(2026, 3, 2)
        assert resolution.ladder_from_date == date(2026, 1, 2)

    def test_resolves_explicit_range(self) -> None:
        """An explicit start/end within the ladder's range resolves unchanged."""
        summary = _summary_with_ladder(date(2026, 1, 2), date(2026, 3, 2))
        resolution = resolve_window(
            accounts_service=_FakeAccountsService(summary),
            date_resolver=TimeseriesDateResolver(),
            account_name="acct",
            start=date(2026, 1, 5),
            end=date(2026, 1, 9),
            today=date(2026, 3, 2),
            attribute_label="var-series",
        )
        assert resolution.resolved_start == date(2026, 1, 5)
        assert resolution.resolved_end == date(2026, 1, 9)

    def test_raises_account_not_found_with_no_resources(self) -> None:
        """No capital ledger and no position ladder raises AccountNotFoundError."""
        summary = _FakeSummary(capital_ledger=None, position_ladder=None)
        with pytest.raises(AccountNotFoundError):
            resolve_window(
                accounts_service=_FakeAccountsService(summary),
                date_resolver=TimeseriesDateResolver(),
                account_name="missing",
                start=None,
                end=None,
                today=date(2026, 3, 2),
                attribute_label="var-series",
            )

    def test_raises_missing_required_source_with_no_ladder(self) -> None:
        """A capital-only account (no position ladder) raises MissingRequiredSourceError."""
        summary = _FakeSummary(
            capital_ledger=_FakeSourceMeta(date(2026, 1, 1), date(2026, 1, 1)),
            position_ladder=None,
        )
        with pytest.raises(MissingRequiredSourceError):
            resolve_window(
                accounts_service=_FakeAccountsService(summary),
                date_resolver=TimeseriesDateResolver(),
                account_name="capital-only",
                start=None,
                end=None,
                today=date(2026, 3, 2),
                attribute_label="var-series",
            )

    def test_raises_future_end_date(self) -> None:
        """An end date after today raises FutureEndDateError."""
        summary = _summary_with_ladder(date(2026, 1, 2), date(2026, 3, 2))
        with pytest.raises(FutureEndDateError):
            resolve_window(
                accounts_service=_FakeAccountsService(summary),
                date_resolver=TimeseriesDateResolver(),
                account_name="acct",
                start=None,
                end=date(2026, 6, 1),
                today=date(2026, 3, 2),
                attribute_label="var-series",
            )

    def test_raises_invalid_date_range_when_start_after_end(self) -> None:
        """A start date after the (explicit) end date raises InvalidDateRangeError."""
        summary = _summary_with_ladder(date(2026, 1, 2), date(2026, 3, 2))
        with pytest.raises(InvalidDateRangeError):
            resolve_window(
                accounts_service=_FakeAccountsService(summary),
                date_resolver=TimeseriesDateResolver(),
                account_name="acct",
                start=date(2026, 2, 1),
                end=date(2026, 1, 1),
                today=date(2026, 3, 2),
                attribute_label="var-series",
            )

    def test_raises_missing_required_source_when_start_precedes_ladder(self) -> None:
        """A start date before the ladder's first date raises MissingRequiredSourceError."""
        summary = _summary_with_ladder(date(2026, 2, 2), date(2026, 3, 2))
        with pytest.raises(MissingRequiredSourceError):
            resolve_window(
                accounts_service=_FakeAccountsService(summary),
                date_resolver=TimeseriesDateResolver(),
                account_name="acct",
                start=date(2026, 1, 1),
                end=date(2026, 3, 2),
                today=date(2026, 3, 2),
                attribute_label="var-series",
            )
