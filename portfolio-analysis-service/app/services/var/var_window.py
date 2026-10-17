"""Ladder-free date-window resolution shared by the VaR series and backtest services.

Mirrors the account/date validation DailyReturnSeriesLoader.load() performs for the
performance and return-histogram endpoints (FR-002, FR-024), but deliberately never
calls LadderRepository.read_full_df() -- only the ladder's own metadata (its from_date)
is needed to resolve the window, and avoiding the full read is what keeps SC-004's
2-second budget achievable (research.md section 1).
"""

from dataclasses import dataclass
from datetime import date

from app.exceptions import AccountNotFoundError, MissingRequiredSourceError
from app.services.accounts_service import AccountsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver


@dataclass(frozen=True)
class WindowResolution:
    """The resolved date window for a VaR series/backtest request.

    Attributes:
        resolved_start: Business-day-aligned start of the requested window.
        resolved_end: Business-day-aligned end of the requested window.
        ladder_from_date: The account's position ladder's own first date.
    """

    resolved_start: date
    resolved_end: date
    ladder_from_date: date


def resolve_window(
    accounts_service: AccountsService,
    date_resolver: TimeseriesDateResolver,
    account_name: str,
    start: date | None,
    end: date | None,
    today: date,
    attribute_label: str,
) -> WindowResolution:
    """Validate the account and resolve its requested date window.

    Args:
        accounts_service: Shared account existence/date-range lookup service.
        date_resolver: Shared date defaulting/adjustment service.
        account_name: The account identifier.
        start: Caller-supplied start date, or None to default.
        end: Caller-supplied end date, or None to default.
        today: The current date.
        attribute_label: Name of the requested measure/endpoint, used in
            MissingRequiredSourceError messages.

    Returns:
        The resolved window and the ladder's own first date.

    Raises:
        AccountNotFoundError: If the account has no ingested resource at all.
        MissingRequiredSourceError: If the account has no position ladder, or the
            resolved start precedes the ladder's first date.
        FutureEndDateError: If end is later than today.
        InvalidDateRangeError: If the resolved start is after the resolved end.
    """
    summary = accounts_service.get_summary(account_name)
    if summary.capital_ledger is None and summary.position_ladder is None:
        raise AccountNotFoundError(
            account_name=account_name,
            message=(
                f"No capital ledger or position ladder has been ingested for "
                f"account '{account_name}'."
            ),
        )
    if summary.position_ladder is None:
        raise MissingRequiredSourceError(
            account_name=account_name, attribute=attribute_label, source="position_ladder"
        )

    resolved_start, resolved_end = date_resolver.resolve(
        raw_start=start,
        raw_end=end,
        today=today,
        required_source_earliest_dates=[summary.position_ladder.from_date],
    )

    if resolved_start < summary.position_ladder.from_date:
        raise MissingRequiredSourceError(
            account_name=account_name,
            attribute=attribute_label,
            source="position_ladder",
            message=(
                f"position_ladder for account '{account_name}' has no data before "
                f"{summary.position_ladder.from_date}, but the resolved start date "
                f"is {resolved_start}."
            ),
        )

    return WindowResolution(
        resolved_start=resolved_start,
        resolved_end=resolved_end,
        ladder_from_date=summary.position_ladder.from_date,
    )
