"""Orchestrates the risk endpoints' computations over the shared daily return series."""

from datetime import date

import structlog

from app.models.risk import ReturnHistogramResponse
from app.services.daily_return_series_loader import DailyReturnSeriesLoader
from app.services.return_histogram import (
    build_histogram,
    compute_statistics,
    to_basis_points,
)

logger = structlog.get_logger(__name__)

_ENDPOINT_LABEL = "return-histogram"


class RiskService:
    """Computes account-level risk measures from the position ladder."""

    def __init__(self, loader: DailyReturnSeriesLoader) -> None:
        """Initialise with the shared daily return series loader.

        Args:
            loader: Shared loader that validates the account, resolves dates and builds the
                same daily portfolio return series the performance endpoints use.
        """
        self._loader = loader

    def get_return_histogram(
        self,
        account_name: str,
        start: date | None,
        end: date | None,
        today: date,
    ) -> ReturnHistogramResponse:
        """Build the histogram of an account's daily returns in whole basis points.

        Args:
            account_name: The account identifier.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            today: The current date.

        Returns:
            Populated ReturnHistogramResponse.

        Raises:
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If the account has no position ladder, or the
                resolved start precedes the ladder's first date.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        loaded = self._loader.load(
            account_name=account_name,
            start=start,
            end=end,
            today=today,
            attribute_label=_ENDPOINT_LABEL,
        )
        series = loaded.daily_returns
        window = series[
            (series["date"] >= loaded.resolved_start) & (series["date"] <= loaded.resolved_end)
        ]
        bps = to_basis_points(window["daily_return"])
        histogram = build_histogram(bps)

        logger.info(
            "return_histogram_request",
            account_name=account_name,
            from_date=str(loaded.resolved_start),
            to_date=str(loaded.resolved_end),
            observation_count=len(bps),
            bucket_count=len(histogram),
        )

        return ReturnHistogramResponse(
            account_name=account_name,
            from_date=loaded.resolved_start,
            to_date=loaded.resolved_end,
            histogram=histogram,
            statistics=compute_statistics(bps),
            _links={
                "self": f"/v1/accounts/{account_name}/risk/return-histogram",
                "accounts": "/v1/accounts",
            },
        )
