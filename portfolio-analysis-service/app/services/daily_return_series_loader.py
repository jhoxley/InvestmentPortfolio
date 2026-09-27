"""Shared acquisition of an account's daily portfolio return series.

Used by both the performance and risk endpoints so that account/source validation, date
resolution, and daily-return aggregation cannot diverge between them.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.exceptions import AccountNotFoundError, MissingRequiredSourceError
from app.repositories.ladder_repository import LadderRepository
from app.services.accounts_service import AccountsService
from app.services.daily_portfolio_return import compute_daily_portfolio_return
from app.services.timeseries_date_resolver import TimeseriesDateResolver


@dataclass(frozen=True)
class LoadedDailyReturns:
    """Resolved date range and the full daily portfolio return series for an account.

    Attributes:
        resolved_start: Business-day-aligned start of the requested window.
        resolved_end: Business-day-aligned end of the requested window.
        daily_returns: DataFrame with columns [date, daily_return], one row per business day
            from the ladder's first date through resolved_end. Not sliced to the window, so
            callers needing look-back (e.g. trailing returns) can use it directly.
    """

    resolved_start: date
    resolved_end: date
    daily_returns: pd.DataFrame


class DailyReturnSeriesLoader:
    """Validates an account, resolves the date window, and builds its daily return series."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        accounts_service: AccountsService,
        date_resolver: TimeseriesDateResolver,
    ) -> None:
        """Initialise with the ladder repository and the shared account/date services.

        Args:
            ladder_repo: Repository for position ladders.
            accounts_service: Shared account existence/date-range lookup service.
            date_resolver: Shared date defaulting/adjustment service.
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service
        self._date_resolver = date_resolver

    def load(
        self,
        account_name: str,
        start: date | None,
        end: date | None,
        today: date,
        attribute_label: str,
    ) -> LoadedDailyReturns:
        """Load the daily portfolio return series for an account and resolve the window.

        Args:
            account_name: The account identifier.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            today: The current date.
            attribute_label: Name of the requested measure/endpoint, used in
                MissingRequiredSourceError messages.

        Returns:
            The resolved window and the full daily return series.

        Raises:
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If the account has no position ladder, or the
                resolved start precedes the ladder's first date.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        summary = self._accounts_service.get_summary(account_name)
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

        resolved_start, resolved_end = self._date_resolver.resolve(
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

        ladder_df = self._ladder_repo.read_full_df(account_name)
        daily_returns = compute_daily_portfolio_return(
            ladder_df,
            from_date=summary.position_ladder.from_date,
            through_date=resolved_end,
        )
        return LoadedDailyReturns(
            resolved_start=resolved_start,
            resolved_end=resolved_end,
            daily_returns=daily_returns,
        )
