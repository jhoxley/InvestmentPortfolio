"""Orchestrates validation, date resolution, and performance-measure computation.

For the account performance endpoint.
"""

from datetime import date

import pandas as pd
import structlog

from app.exceptions import AccountNotFoundError, MissingRequiredSourceError
from app.models.performance import PerformanceEntry, PerformanceResponse
from app.repositories.ladder_repository import LadderRepository
from app.services import performance_attributes
from app.services.accounts_service import AccountsService
from app.services.daily_portfolio_return import compute_daily_portfolio_return
from app.services.performance_metrics import compute_performance_measures
from app.services.timeseries_date_resolver import TimeseriesDateResolver

logger = structlog.get_logger(__name__)


class PerformanceService:
    """Computes account-level performance measures from the position ladder."""

    def __init__(
        self,
        ladder_repo: LadderRepository,
        accounts_service: AccountsService,
        date_resolver: TimeseriesDateResolver,
    ) -> None:
        """Initialise with the ladder repository and the shared account/date services.

        Args:
            ladder_repo: Repository for position ladders. Every performance measure
                requires only the position ladder — no capital_repo is needed.
            accounts_service: Shared account existence/date-range lookup service.
            date_resolver: Shared date defaulting/adjustment service.
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service
        self._date_resolver = date_resolver

    def get_performance(
        self,
        account_name: str,
        attributes: list[str],
        start: date | None,
        end: date | None,
        today: date,
    ) -> PerformanceResponse:
        """Build the requested performance series for an account.

        Args:
            account_name: The account identifier.
            attributes: Requested measure names.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            today: The current date.

        Returns:
            Populated PerformanceResponse.

        Raises:
            NoAttributesRequestedError: If attributes is empty.
            UnsupportedAttributeError: If any attribute name is unsupported.
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If the account has no position ladder.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        log = logger.bind(account_name=account_name, attributes=attributes)
        performance_attributes.validate_attributes(attributes)

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
                account_name=account_name, attribute=attributes[0], source="position_ladder"
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
                attribute=attributes[0],
                source="position_ladder",
                message=(
                    f"position_ladder for account '{account_name}' has no data before "
                    f"{summary.position_ladder.from_date}, but the resolved start date "
                    f"is {resolved_start}."
                ),
            )

        ladder_df = self._ladder_repo.read_full_df(account_name)
        daily_returns_df = compute_daily_portfolio_return(
            ladder_df,
            from_date=summary.position_ladder.from_date,
            through_date=resolved_end,
        )
        measures_df = compute_performance_measures(daily_returns_df)

        windowed = measures_df[
            (measures_df["date"] >= resolved_start) & (measures_df["date"] <= resolved_end)
        ]

        entries = [
            PerformanceEntry(
                date=row["date"],
                **{attr: float(row[attr]) for attr in attributes if pd.notna(row[attr])},
            )
            for _, row in windowed.iterrows()
        ]

        log.info(
            "performance_request",
            from_date=str(resolved_start),
            to_date=str(resolved_end),
            row_count=len(entries),
        )

        return PerformanceResponse(
            account_name=account_name,
            attributes=attributes,
            from_date=resolved_start,
            to_date=resolved_end,
            entries=entries,
            _links={
                "self": f"/v1/accounts/{account_name}/performance",
                "attributes": "/v1/performance/attributes",
                "accounts": "/v1/accounts",
            },
        )
