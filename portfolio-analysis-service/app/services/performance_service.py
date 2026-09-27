"""Orchestrates validation, date resolution, and performance-measure computation.

For the account performance endpoint.
"""

from datetime import date

import pandas as pd
import structlog

from app.models.performance import PerformanceEntry, PerformanceResponse
from app.repositories.ladder_repository import LadderRepository
from app.services import performance_attributes
from app.services.accounts_service import AccountsService
from app.services.daily_return_series_loader import DailyReturnSeriesLoader
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
        self._loader = DailyReturnSeriesLoader(
            ladder_repo=ladder_repo,
            accounts_service=accounts_service,
            date_resolver=date_resolver,
        )

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
            MissingRequiredSourceError: If the account has no position ladder, or the
                resolved start precedes the ladder's first date.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        log = logger.bind(account_name=account_name, attributes=attributes)
        performance_attributes.validate_attributes(attributes)

        loaded = self._loader.load(
            account_name=account_name,
            start=start,
            end=end,
            today=today,
            attribute_label=attributes[0],
        )
        resolved_start, resolved_end = loaded.resolved_start, loaded.resolved_end
        daily_returns_df = loaded.daily_returns
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
