"""HTTP client for calling portfolio-analysis-service's account/timeseries API.

Mirrors the Protocol + concrete-class pattern already used by
portfolio-analysis-service's own outbound client
(app/clients/market_data_client.py) — data access only, no calculation.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Protocol

import httpx
import structlog

from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountSummary,
    AttributeDefinition,
    PositionSummary,
    PositionTimeSeriesResponse,
    ReturnHistogramResponse,
    TimeSeriesResponse,
)

logger = structlog.get_logger(__name__)


def _warn_if_periodicity_ignored(
    requested: str | None, echoed: str | None, account_name: str, path: str
) -> None:
    """Log a warning when the service did not apply the interval we asked for.

    From its feature 008 onward the service echoes the applied `periodicity` on
    every response. An older service silently ignores the parameter and returns
    daily data with no field at all — which would otherwise leave the UI showing
    one interval while plotting another, with nothing to diagnose it by.

    Args:
        requested: The interval this client asked for, if any.
        echoed: The interval the response reported, if any.
        account_name: Account being queried (log context).
        path: Endpoint path (log context).
    """
    if requested is None or echoed == requested:
        return
    logger.warning(
        "periodicity_not_applied",
        account_name=account_name,
        path=path,
        requested_periodicity=requested,
        echoed_periodicity=echoed,
        detail=(
            "The analysis service did not report applying the requested periodicity. "
            "A response with no periodicity field means the service predates its "
            "feature 008 and is ignoring the parameter; restart it with the current build."
        ),
    )


class PortfolioAnalysisClient(Protocol):
    """Abstraction over the outbound portfolio-analysis-service calls."""

    def list_accounts(self) -> list[AccountSummary]:
        """Return every account with at least one ingested resource."""
        ...

    def list_attributes(self) -> list[AttributeDefinition]:
        """Return every chartable timeseries attribute."""
        ...

    def get_timeseries(
        self,
        account_name: str,
        attributes: list[str],
        start: date,
        end: date,
        periodicity: str | None = None,
    ) -> TimeSeriesResponse:
        """Return the timeseries for an account over a date range.

        Args:
            account_name: The account to request a timeseries for.
            attributes: One or more attribute names to request.
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).
            periodicity: Optional aggregation interval (the service's own value,
                e.g. "annual"). Omitted from the request entirely when None,
                which the service treats as per-business-day.

        Returns:
            The parsed TimeSeriesResponse.
        """
        ...

    def list_account_positions(self, account_name: str) -> list[PositionSummary]:
        """Return every position recorded for an account.

        Args:
            account_name: The account to enumerate positions for.

        Returns:
            List of PositionSummary parsed from the response.
        """
        ...

    def list_position_attributes(self) -> list[AttributeDefinition]:
        """Return every chartable/tabulable position attribute."""
        ...

    def list_performance_attributes(self) -> list[AttributeDefinition]:
        """Return every chartable performance measure."""
        ...

    def get_performance(
        self,
        account_name: str,
        attributes: list[str],
        start: date,
        end: date,
    ) -> TimeSeriesResponse:
        """Return the performance measure timeseries for an account over a date range.

        Reuses `TimeSeriesResponse`/`TimeSeriesEntry` — the upstream response
        shape is identical to the account timeseries endpoint's (specs/020-
        performance-page-chart/research.md #1).

        Args:
            account_name: The account to request performance measures for.
            attributes: One or more measure names to request (e.g. "ITD").
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).

        Returns:
            The parsed TimeSeriesResponse.
        """
        ...

    def get_position_timeseries(
        self,
        account_name: str,
        positions: list[str],
        attributes: list[str],
        start: date,
        end: date,
        periodicity: str | None = None,
    ) -> PositionTimeSeriesResponse:
        """Return the per-position timeseries for an account over a date range.

        Args:
            account_name: The account to request a position timeseries for.
            positions: Position names to include, sent explicitly even when
                every known position is selected (no "omit if all selected"
                special-casing). An empty list is forwarded as-is (the
                endpoint's own default is "every position").
            attributes: One or more attribute names to request.
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).
            periodicity: Optional aggregation interval, applied independently
                per position. Omitted from the request entirely when None.

        Returns:
            The parsed PositionTimeSeriesResponse.
        """
        ...

    def get_projection(
        self,
        account_name: str,
        projection_date: date,
        returns: list[str],
        start: date | None = None,
        periodicity: str | None = None,
    ) -> PositionTimeSeriesResponse:
        """Return the historical-plus-projected market-value series for an account.

        Reuses `PositionTimeSeriesResponse` (specs/022-projection-page/
        research.md #1) — the response's `position` field carries a series
        label ("Historical" or a requested return's label) rather than a
        position name.

        Args:
            account_name: The account to project.
            projection_date: The date to project forward to. Must be later
                than the resolved start date (the service validates this).
            returns: Zero or more return names to project
                ("ITD (Ann.)"/"1Y"/"3Y"/"5Y" — the exact measure names the
                service's own performance endpoint uses). An empty list
                still returns the "Historical" series alone.
            start: The date historical data ends and every projection begins.
                Omitted from the request entirely when None, which the
                service defaults to the account's most recently recorded
                date.
            periodicity: Optional aggregation interval, applied to both the
                historical and projected legs. Omitted from the request
                entirely when None.

        Returns:
            The parsed PositionTimeSeriesResponse.
        """
        ...

    def get_return_histogram(
        self,
        account_name: str,
        start: date,
        end: date,
    ) -> ReturnHistogramResponse:
        """Return the daily-return histogram and statistics for an account over a date range.

        Args:
            account_name: The account to request a return histogram for.
            start: Start of the requested observation window (inclusive).
            end: End of the requested observation window (inclusive).

        Returns:
            The parsed ReturnHistogramResponse.
        """
        ...


class HttpPortfolioAnalysisClient:
    """PortfolioAnalysisClient implementation backed by an HTTP call."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Initialise the underlying httpx client.

        Args:
            base_url: Base URL of the portfolio-analysis-service instance.
            timeout_seconds: Request timeout in seconds.
            transport: Optional custom transport (e.g. httpx.MockTransport for tests).
        """
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)

    def list_accounts(self) -> list[AccountSummary]:
        """Return every account with at least one ingested resource.

        Returns:
            List of AccountSummary parsed from the response.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        payload = self._get("/v1/accounts", params=None, log_context={})
        return [AccountSummary.model_validate(a) for a in payload.get("accounts", [])]

    def list_attributes(self) -> list[AttributeDefinition]:
        """Return every chartable timeseries attribute.

        Returns:
            List of AttributeDefinition parsed from the response.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        payload = self._get("/v1/timeseries/attributes", params=None, log_context={})
        return [AttributeDefinition.model_validate(a) for a in payload.get("attributes", [])]

    def get_timeseries(
        self,
        account_name: str,
        attributes: list[str],
        start: date,
        end: date,
        periodicity: str | None = None,
    ) -> TimeSeriesResponse:
        """Return the timeseries for an account over a date range.

        Args:
            account_name: The account to request a timeseries for.
            attributes: One or more attribute names to request.
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).
            periodicity: Optional aggregation interval (the service's own value,
                e.g. "annual"). Omitted from the request entirely when None.

        Returns:
            The parsed TimeSeriesResponse.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        path = f"/v1/accounts/{account_name}/timeseries"
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("attribute", a) for a in attributes
        ]
        params.extend([("start", str(start)), ("end", str(end))])
        if periodicity is not None:
            params.append(("periodicity", periodicity))
        payload = self._get(
            path,
            params=params,
            log_context={"account_name": account_name},
        )
        response = TimeSeriesResponse.model_validate(payload)
        _warn_if_periodicity_ignored(periodicity, response.periodicity, account_name, path)
        return response

    def list_account_positions(self, account_name: str) -> list[PositionSummary]:
        """Return every position recorded for an account.

        Args:
            account_name: The account to enumerate positions for.

        Returns:
            List of PositionSummary parsed from the response.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        payload = self._get(
            f"/v1/accounts/{account_name}/positions",
            params=None,
            log_context={"account_name": account_name},
        )
        return [PositionSummary.model_validate(p) for p in payload.get("positions", [])]

    def list_position_attributes(self) -> list[AttributeDefinition]:
        """Return every chartable/tabulable position attribute.

        Returns:
            List of AttributeDefinition parsed from the response.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        payload = self._get("/v1/positions/attributes", params=None, log_context={})
        return [AttributeDefinition.model_validate(a) for a in payload.get("attributes", [])]

    def list_performance_attributes(self) -> list[AttributeDefinition]:
        """Return every chartable performance measure.

        Returns:
            List of AttributeDefinition parsed from the response.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        payload = self._get("/v1/performance/attributes", params=None, log_context={})
        return [AttributeDefinition.model_validate(a) for a in payload.get("attributes", [])]

    def get_performance(
        self,
        account_name: str,
        attributes: list[str],
        start: date,
        end: date,
    ) -> TimeSeriesResponse:
        """Return the performance measure timeseries for an account over a date range.

        Args:
            account_name: The account to request performance measures for.
            attributes: One or more measure names to request (e.g. "ITD").
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).

        Returns:
            The parsed TimeSeriesResponse.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("attribute", a) for a in attributes
        ]
        params.extend([("start", str(start)), ("end", str(end))])
        payload = self._get(
            f"/v1/accounts/{account_name}/performance",
            params=params,
            log_context={"account_name": account_name},
        )
        return TimeSeriesResponse.model_validate(payload)

    def get_position_timeseries(
        self,
        account_name: str,
        positions: list[str],
        attributes: list[str],
        start: date,
        end: date,
        periodicity: str | None = None,
    ) -> PositionTimeSeriesResponse:
        """Return the per-position timeseries for an account over a date range.

        Args:
            account_name: The account to request a position timeseries for.
            positions: Position names to include, sent explicitly even when
                every known position is selected.
            attributes: One or more attribute names to request.
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).
            periodicity: Optional aggregation interval, applied independently
                per position. Omitted from the request entirely when None.

        Returns:
            The parsed PositionTimeSeriesResponse.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        path = f"/v1/accounts/{account_name}/position"
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("position", p) for p in positions
        ]
        params.extend(("attribute", a) for a in attributes)
        params.extend([("start", str(start)), ("end", str(end))])
        if periodicity is not None:
            params.append(("periodicity", periodicity))
        payload = self._get(
            path,
            params=params,
            log_context={"account_name": account_name},
        )
        response = PositionTimeSeriesResponse.model_validate(payload)
        _warn_if_periodicity_ignored(periodicity, response.periodicity, account_name, path)
        return response

    def get_projection(
        self,
        account_name: str,
        projection_date: date,
        returns: list[str],
        start: date | None = None,
        periodicity: str | None = None,
    ) -> PositionTimeSeriesResponse:
        """Return the historical-plus-projected market-value series for an account.

        Args:
            account_name: The account to project.
            projection_date: The date to project forward to.
            returns: Zero or more return names to project. Sent as one
                `return` query param each; omitted entirely when empty.
            start: Start date historical data ends and every projection
                begins. Omitted from the request entirely when None.
            periodicity: Optional aggregation interval. Omitted from the
                request entirely when None.

        Returns:
            The parsed PositionTimeSeriesResponse (its `position` field
            carries series labels, not position names — specs/022-
            projection-page/research.md #1).

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        path = f"/v1/accounts/{account_name}/projection"
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("return", r) for r in returns
        ]
        params.append(("projection_date", str(projection_date)))
        if start is not None:
            params.append(("start", str(start)))
        if periodicity is not None:
            params.append(("periodicity", periodicity))
        payload = self._get(
            path,
            params=params,
            log_context={"account_name": account_name},
        )
        response = PositionTimeSeriesResponse.model_validate(payload)
        _warn_if_periodicity_ignored(periodicity, response.periodicity, account_name, path)
        return response

    def get_return_histogram(
        self,
        account_name: str,
        start: date,
        end: date,
    ) -> ReturnHistogramResponse:
        """Return the daily-return histogram and statistics for an account over a date range.

        Args:
            account_name: The account to request a return histogram for.
            start: Start of the requested observation window (inclusive).
            end: End of the requested observation window (inclusive).

        Returns:
            The parsed ReturnHistogramResponse.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        path = f"/v1/accounts/{account_name}/risk/return-histogram"
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("start", str(start)),
            ("end", str(end)),
        ]
        payload = self._get(
            path,
            params=params,
            log_context={"account_name": account_name},
        )
        return ReturnHistogramResponse.model_validate(payload)

    def _get(
        self,
        path: str,
        params: list[tuple[str, str | int | float | bool | None]] | None,
        log_context: dict[str, str],
    ) -> dict:
        start_time = time.perf_counter()
        log = logger.bind(path=path, **log_context)
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log.error("portfolio_analysis_request_failed", duration_ms=duration_ms, detail=str(exc))
            raise PortfolioAnalysisServiceError(str(exc)) from exc

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log.info("portfolio_analysis_request_succeeded", duration_ms=duration_ms)
        return response.json()
