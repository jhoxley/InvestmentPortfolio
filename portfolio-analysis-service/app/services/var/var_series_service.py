"""Orchestrates the read-only VaR series endpoint (013-var-series-backtest-api)."""

import math
from datetime import date

import pandas as pd
import structlog

from app.config import VarSettings
from app.models.var_series import ConfidenceLevelEstimate, VarSeriesEntry, VarSeriesResponse
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.var.var_window import resolve_window

logger = structlog.get_logger(__name__)

_ENDPOINT_LABEL = "var-series"


def _is_nan(value: object) -> bool:
    """True if value is a float NaN (pandas' representation of a missing CSV cell)."""
    return isinstance(value, float) and math.isnan(value)


def _none_if_nan_str(value: object) -> str | None:
    """Convert a pandas NaN/None read back from CSV into None; pass strings through.

    Args:
        value: A cell value read from a pandas DataFrame.

    Returns:
        None if value is missing (NaN or None), otherwise str(value).
    """
    if value is None or _is_nan(value):
        return None
    return str(value)


def _none_if_nan(value: object) -> float | None:
    """Convert a pandas NaN (float) read back from CSV into None; pass other values through.

    Args:
        value: A cell value read from a pandas DataFrame.

    Returns:
        None if value is a float NaN, otherwise value cast to float, or None if value
        is itself None/NaT.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return float(value)


class VarSeriesService:
    """Builds the VaR series response from feature 012's existing estimates/outcomes store."""

    def __init__(
        self, accounts_service: AccountsService, var_repo: VarRepository, settings: VarSettings
    ) -> None:
        """Initialise with the shared accounts service, VaR repository and VaR settings.

        Args:
            accounts_service: Shared account existence/date-range lookup service.
            var_repo: Repository over the per-account VaR store (read-only here).
            settings: The application's VaR configuration.
        """
        self._accounts_service = accounts_service
        self._var_repo = var_repo
        self._settings = settings
        self._date_resolver = TimeseriesDateResolver()

    def get_series(
        self,
        account_name: str,
        start: date | None,
        end: date | None,
        lookback: str | None,
        confidence_levels_bp: list[int] | None,
        today: date,
    ) -> VarSeriesResponse:
        """Build the series of previously computed estimates joined with realised outcomes.

        Args:
            account_name: The account identifier.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            lookback: A configured look-back code, or None for the configured headline.
            confidence_levels_bp: Confidence levels in basis points, or None for every
                configured level.
            today: The current date.

        Returns:
            Populated VarSeriesResponse (series is empty if nothing has been computed).

        Raises:
            AccountNotFoundError: If the account has no ingested resource at all.
            MissingRequiredSourceError: If the account has no position ladder, or the
                resolved start precedes the ladder's first date.
            FutureEndDateError: If end is later than today.
            InvalidDateRangeError: If the resolved start is after the resolved end.
        """
        window = resolve_window(
            accounts_service=self._accounts_service,
            date_resolver=self._date_resolver,
            account_name=account_name,
            start=start,
            end=end,
            today=today,
            attribute_label=_ENDPOINT_LABEL,
        )
        lookback_code = lookback or self._settings.headline_lookback
        lookback_days = self._settings.lookbacks[lookback_code]
        levels_bp = confidence_levels_bp or list(self._settings.confidence_levels_bp)

        links = {
            "self": f"/v1/accounts/{account_name}/risk/var",
            "status": f"/v1/accounts/{account_name}/risk/var/status",
            "runs": f"/v1/accounts/{account_name}/risk/var/runs",
        }

        estimates = self._var_repo.read_estimates(account_name)
        outcomes = self._var_repo.read_outcomes(account_name)

        entries: list[VarSeriesEntry] = []
        if not estimates.empty:
            start_ts = pd.Timestamp(window.resolved_start)
            end_ts = pd.Timestamp(window.resolved_end)
            window_mask = (
                (estimates["lookback_code"] == lookback_code)
                & (estimates["date"] >= start_ts)
                & (estimates["date"] <= end_ts)
            )
            scoped = estimates[window_mask].sort_values("date")
            merged = scoped.merge(outcomes, on="date", how="left", suffixes=("", "_outcome"))
            entries = [self._build_entry(row, levels_bp) for row in merged.to_dict("records")]

        logger.info(
            "var_series_request",
            account_name=account_name,
            lookback_code=lookback_code,
            confidence_levels_bp=levels_bp,
            from_date=str(window.resolved_start),
            to_date=str(window.resolved_end),
            row_count=len(entries),
        )

        return VarSeriesResponse(
            account_name=account_name,
            lookback_code=lookback_code,
            lookback_days=lookback_days,
            from_date=window.resolved_start,
            to_date=window.resolved_end,
            series=entries,
            _links=links,
        )

    def _build_entry(self, row: dict[str, object], levels_bp: list[int]) -> VarSeriesEntry:
        """Build one VarSeriesEntry from a merged estimate/outcome row.

        Args:
            row: A dict of one merged pandas row (estimate columns plus outcome columns).
            levels_bp: Confidence levels in basis points to include.

        Returns:
            Populated VarSeriesEntry.
        """
        total_value_gbp = _none_if_nan(row.get("total_value_gbp")) or 0.0
        hypothetical_pnl_gbp = _none_if_nan(row.get("hypothetical_pnl_gbp"))
        ladder_pnl_gbp = _none_if_nan(row.get("ladder_pnl_gbp"))
        outcome_date = row.get("outcome_date")
        if outcome_date is None or (isinstance(outcome_date, float) and math.isnan(outcome_date)):
            outcome_date = pd.Timestamp(row["date"]) + pd.offsets.BDay(1)

        levels = [
            self._build_level(row, bp, hypothetical_pnl_gbp, ladder_pnl_gbp, total_value_gbp)
            for bp in levels_bp
        ]

        return VarSeriesEntry(
            date=pd.Timestamp(row["date"]).date(),
            outcome_date=pd.Timestamp(outcome_date).date(),
            total_value_gbp=total_value_gbp,
            scenario_count=int(row["scenario_count"]),
            actual_mv_pct=float(row["actual_mv_pct"]),
            proxied_mv_pct=float(row["proxied_mv_pct"]),
            rescaled_mv_pct=float(row["rescaled_mv_pct"]),
            quality=row["quality"],  # type: ignore[arg-type]
            quality_reason=row.get("quality_reason") if row.get("quality_reason") else None,
            hypothetical_pnl_gbp=hypothetical_pnl_gbp,
            ladder_pnl_gbp=ladder_pnl_gbp,
            levels=levels,
        )

    def _build_level(
        self,
        row: dict[str, object],
        confidence_bp: int,
        hypothetical_pnl_gbp: float | None,
        ladder_pnl_gbp: float | None,
        total_value_gbp: float,
    ) -> ConfidenceLevelEstimate:
        """Build one ConfidenceLevelEstimate from a merged row at one confidence level.

        Args:
            row: A dict of one merged pandas row.
            confidence_bp: Confidence level in basis points.
            hypothetical_pnl_gbp: The date's realised hypothetical PnL, or None if pending.
            ladder_pnl_gbp: The date's realised ladder PnL, or None if pending.
            total_value_gbp: The date's total market value, used for the percentage figures.

        Returns:
            Populated ConfidenceLevelEstimate.
        """
        var_gbp = _none_if_nan(row.get(f"var_{confidence_bp}_gbp"))
        es_gbp = _none_if_nan(row.get(f"es_{confidence_bp}_gbp"))
        var_pct = var_gbp / total_value_gbp * 100 if var_gbp is not None and total_value_gbp else None
        es_pct = es_gbp / total_value_gbp * 100 if es_gbp is not None and total_value_gbp else None

        hypothetical_exception = (
            None
            if var_gbp is None or hypothetical_pnl_gbp is None
            else hypothetical_pnl_gbp < -var_gbp
        )
        ladder_exception = (
            None if var_gbp is None or ladder_pnl_gbp is None else ladder_pnl_gbp < -var_gbp
        )

        return ConfidenceLevelEstimate(
            confidence_bp=confidence_bp,
            var_gbp=var_gbp,
            var_pct=var_pct,
            es_gbp=es_gbp,
            es_pct=es_pct,
            hypothetical_exception=hypothetical_exception,
            ladder_exception=ladder_exception,
        )
