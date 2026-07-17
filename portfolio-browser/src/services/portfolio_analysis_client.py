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
    TimeSeriesResponse,
)

logger = structlog.get_logger(__name__)


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
    ) -> TimeSeriesResponse:
        """Return the timeseries for an account over a date range.

        Args:
            account_name: The account to request a timeseries for.
            attributes: One or more attribute names to request.
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).

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

    def get_position_timeseries(
        self,
        account_name: str,
        positions: list[str],
        attributes: list[str],
        start: date,
        end: date,
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

        Returns:
            The parsed PositionTimeSeriesResponse.
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
    ) -> TimeSeriesResponse:
        """Return the timeseries for an account over a date range.

        Args:
            account_name: The account to request a timeseries for.
            attributes: One or more attribute names to request.
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
            f"/v1/accounts/{account_name}/timeseries",
            params=params,
            log_context={"account_name": account_name},
        )
        return TimeSeriesResponse.model_validate(payload)

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

    def get_position_timeseries(
        self,
        account_name: str,
        positions: list[str],
        attributes: list[str],
        start: date,
        end: date,
    ) -> PositionTimeSeriesResponse:
        """Return the per-position timeseries for an account over a date range.

        Args:
            account_name: The account to request a position timeseries for.
            positions: Position names to include, sent explicitly even when
                every known position is selected.
            attributes: One or more attribute names to request.
            start: Start of the requested date range (inclusive).
            end: End of the requested date range (inclusive).

        Returns:
            The parsed PositionTimeSeriesResponse.

        Raises:
            PortfolioAnalysisServiceError: On any non-2xx response, timeout, or
                connection error.
        """
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("position", p) for p in positions
        ]
        params.extend(("attribute", a) for a in attributes)
        params.extend([("start", str(start)), ("end", str(end))])
        payload = self._get(
            f"/v1/accounts/{account_name}/position",
            params=params,
            log_context={"account_name": account_name},
        )
        return PositionTimeSeriesResponse.model_validate(payload)

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
