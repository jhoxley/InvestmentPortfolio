"""Orchestrates the read-only VaR backtest endpoint (013-var-series-backtest-api)."""

import math
from datetime import date

import numpy as np
import pandas as pd
import structlog

from app.config import VarSettings
from app.models.var_series import (
    BacktestConfidenceResult,
    RollingExceptionPoint,
    VarBacktestResponse,
)
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.timeseries_date_resolver import TimeseriesDateResolver
from app.services.var.backtest import (
    christoffersen_independence,
    conditional_coverage,
    kupiec_pof,
    rolling_exception_counts,
    traffic_light_zone,
    var_stability,
)
from app.services.var.var_window import resolve_window

logger = structlog.get_logger(__name__)

_ENDPOINT_LABEL = "var-backtest"
_QUALITY_RANK = {"ok": 2, "degraded": 1, "insufficient": 0}
_ROLLING_WINDOW = 250


def _is_nan(value: object) -> bool:
    """True if value is a float NaN (pandas' representation of a missing CSV cell)."""
    return isinstance(value, float) and math.isnan(value)


def _ordinal(d: pd.Timestamp, epoch: pd.Timestamp) -> int:
    """Business-day ordinal of d relative to epoch (Mon-Fri only), via numpy.busday_count."""
    start = epoch.to_numpy().astype("datetime64[D]")
    end = d.to_numpy().astype("datetime64[D]")
    return int(np.busday_count(start, end))


class VarBacktestService:
    """Builds the VaR backtest response from feature 012's existing estimates/outcomes store."""

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

    def get_backtest(
        self,
        account_name: str,
        start: date | None,
        end: date | None,
        lookback: str | None,
        confidence_levels_bp: list[int] | None,
        pnl_basis: str,
        min_quality: str,
        rolling: bool,
        today: date,
    ) -> VarBacktestResponse:
        """Build the backtest statistics for the requested account, window and look-back.

        Args:
            account_name: The account identifier.
            start: Caller-supplied start date, or None to default.
            end: Caller-supplied end date, or None to default.
            lookback: A configured look-back code, or None for the configured headline.
            confidence_levels_bp: Confidence levels in basis points, or None for every
                configured level.
            pnl_basis: "hypothetical" or "ladder" -- which realised PnL series defines
                exceptions.
            min_quality: "ok" or "degraded" -- the minimum quality to include, on top
                of the automatic exclusion of "insufficient" and pending-outcome dates.
            rolling: Whether to include the 250-day rolling exception count series.
            today: The current date.

        Returns:
            Populated VarBacktestResponse.

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

        observations = self._build_observation_set(
            account_name, lookback_code, window.resolved_start, window.resolved_end, min_quality
        )

        levels = [self._build_level(observations, bp, pnl_basis, rolling) for bp in levels_bp]

        logger.info(
            "var_backtest_request",
            account_name=account_name,
            lookback_code=lookback_code,
            pnl_basis=pnl_basis,
            min_quality=min_quality,
            observation_counts={lvl.confidence_bp: lvl.observation_count for lvl in levels},
            exception_counts={lvl.confidence_bp: lvl.exception_count for lvl in levels},
        )

        return VarBacktestResponse(
            account_name=account_name,
            lookback_code=lookback_code,
            lookback_days=lookback_days,
            from_date=window.resolved_start,
            to_date=window.resolved_end,
            pnl_basis=pnl_basis,  # type: ignore[arg-type]
            min_quality=min_quality,  # type: ignore[arg-type]
            levels=levels,
            _links={
                "self": f"/v1/accounts/{account_name}/risk/var/backtest",
                "status": f"/v1/accounts/{account_name}/risk/var/status",
                "runs": f"/v1/accounts/{account_name}/risk/var/runs",
            },
        )

    def _build_observation_set(
        self,
        account_name: str,
        lookback_code: str,
        resolved_start: date,
        resolved_end: date,
        min_quality: str,
    ) -> pd.DataFrame:
        """Build the filtered, ordinal-tagged observation set (research.md section 6).

        Args:
            account_name: The account identifier.
            lookback_code: The look-back code to scope estimates to.
            resolved_start: Window start.
            resolved_end: Window end.
            min_quality: "ok" or "degraded".

        Returns:
            DataFrame sorted by date ascending, with an added "ordinal" column, holding
            only rows that qualify as backtest observations.
        """
        estimates = self._var_repo.read_estimates(account_name)
        outcomes = self._var_repo.read_outcomes(account_name)
        if estimates.empty:
            return estimates

        start_ts = pd.Timestamp(resolved_start)
        end_ts = pd.Timestamp(resolved_end)
        window_mask = (
            (estimates["lookback_code"] == lookback_code)
            & (estimates["date"] >= start_ts)
            & (estimates["date"] <= end_ts)
        )
        scoped = estimates[window_mask].merge(outcomes, on="date", how="left", suffixes=("", "_o"))

        min_rank = _QUALITY_RANK[min_quality]
        quality_rank = scoped["quality"].map(_QUALITY_RANK)
        pending = scoped["outcome_status"] == "pending"
        qualifies = (quality_rank >= max(min_rank, _QUALITY_RANK["degraded"])) & ~pending

        observations = scoped[qualifies].sort_values("date").reset_index(drop=True)
        if observations.empty:
            return observations

        epoch = pd.Timestamp(observations["date"].iloc[0])
        observations = observations.assign(
            ordinal=observations["date"].apply(lambda d: _ordinal(d, epoch))
        )
        return observations

    def _build_level(
        self, observations: pd.DataFrame, confidence_bp: int, pnl_basis: str, rolling: bool
    ) -> BacktestConfidenceResult:
        """Build one confidence level's backtest statistics over the observation set.

        Args:
            observations: The filtered, ordinal-tagged observation set.
            confidence_bp: Confidence level in basis points.
            pnl_basis: "hypothetical" or "ladder".
            rolling: Whether to include the rolling exception count series.

        Returns:
            Populated BacktestConfidenceResult.
        """
        n = len(observations)
        alpha = 1 - confidence_bp / 10000

        if n == 0:
            return BacktestConfidenceResult(
                confidence_bp=confidence_bp,
                observation_count=0,
                exception_count=0,
                expected_exceptions=None,
                exception_rate=None,
                kupiec_lr=None,
                kupiec_p_value=None,
                christoffersen_independence_lr=None,
                christoffersen_independence_p_value=None,
                conditional_coverage_lr=None,
                conditional_coverage_p_value=None,
                zone=None,
                exception_dates=[],
                mean_var_gbp=None,
                var_stability=None,
                rolling_exceptions=None,
            )

        pnl_col = "hypothetical_pnl_gbp" if pnl_basis == "hypothetical" else "ladder_pnl_gbp"
        var_col = f"var_{confidence_bp}_gbp"
        var_values = observations[var_col].to_numpy(dtype=float)
        pnl_values = observations[pnl_col].to_numpy(dtype=float)
        indicators = (pnl_values < -var_values).tolist()
        x = sum(indicators)

        dated_indicators = list(zip(observations["ordinal"].tolist(), indicators, strict=True))
        kupiec_lr, kupiec_p = kupiec_pof(n, x, alpha)
        ind_lr, ind_p = christoffersen_independence(dated_indicators)
        cc_lr, cc_p = conditional_coverage(kupiec_lr, ind_lr)
        zone = traffic_light_zone(n, x, alpha)

        exception_dates = [
            pd.Timestamp(d).date()
            for d, flagged in zip(observations["date"].tolist(), indicators, strict=True)
            if flagged
        ]

        ordinals = observations["ordinal"].tolist()
        fingerprints = observations["row_fingerprint"].tolist()
        stability_input: list[tuple[float, bool]] = []
        for i, var_value in enumerate(var_values.tolist()):
            if i == 0:
                stability_input.append((var_value, False))
                continue
            adjacent = ordinals[i] - ordinals[i - 1] == 1
            holdings_changed = (not adjacent) or (fingerprints[i] != fingerprints[i - 1])
            stability_input.append((var_value, holdings_changed))
        stability = var_stability(stability_input)

        rolling_series: list[RollingExceptionPoint] | None = None
        if rolling:
            counts = rolling_exception_counts(indicators, window=_ROLLING_WINDOW)
            dates = observations["date"].tolist()[_ROLLING_WINDOW - 1 :]
            rolling_series = [
                RollingExceptionPoint(date=pd.Timestamp(d).date(), exception_count=c)
                for d, c in zip(dates, counts, strict=True)
            ]

        return BacktestConfidenceResult(
            confidence_bp=confidence_bp,
            observation_count=n,
            exception_count=x,
            expected_exceptions=n * alpha,
            exception_rate=x / n,
            kupiec_lr=kupiec_lr,
            kupiec_p_value=kupiec_p,
            christoffersen_independence_lr=ind_lr,
            christoffersen_independence_p_value=ind_p,
            conditional_coverage_lr=cc_lr,
            conditional_coverage_p_value=cc_p,
            zone=zone,  # type: ignore[arg-type]
            exception_dates=exception_dates,
            mean_var_gbp=float(var_values.mean()),
            var_stability=stability,
            rolling_exceptions=rolling_series,
        )
