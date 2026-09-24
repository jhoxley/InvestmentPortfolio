"""Orchestrates validation, date resolution, the historical series, and projection computation.

For the account projection endpoint. See specs/009-projection-endpoint/research.md for the
design rationale behind each piece reused here.
"""

from datetime import date

import pandas as pd
import structlog

from app.exceptions import (
    AccountNotFoundError,
    InvalidProjectionRangeError,
    MissingRequiredSourceError,
    PositionLadderNotIngestedError,
)
from app.models.periodicity import Periodicity
from app.models.position_timeseries import PositionTimeSeriesEntry, PositionTimeSeriesResponse
from app.models.timeseries import AccountResourceRange
from app.repositories.ladder_repository import LadderRepository
from app.services import projection_returns
from app.services.accounts_service import AccountsService
from app.services.business_day_expansion import expand_business_days
from app.services.daily_portfolio_return import compute_daily_portfolio_return
from app.services.performance_metrics import compute_performance_measures
from app.services.periodicity_aggregation import aggregate_last_observation

logger = structlog.get_logger(__name__)

_TRADING_DAYS_PER_YEAR = 260
_HISTORICAL_LABEL = "Historical"


class ProjectionService:
    """Builds an account's historical-plus-projected market-value series from its ladder."""

    def __init__(self, ladder_repo: LadderRepository, accounts_service: AccountsService) -> None:
        """Initialise with the ladder repository and the shared account lookup service.

        Args:
            ladder_repo: Repository for position ladders. Every projection requires only the
                position ladder — no capital_repo is needed, mirroring PerformanceService.
            accounts_service: Shared account existence/date-range lookup service.
        """
        self._ladder_repo = ladder_repo
        self._accounts_service = accounts_service

    def get_projection(
        self,
        account_name: str,
        projection_date: date,
        returns: list[str],
        start: date | None = None,
        periodicity: Periodicity = Periodicity.DAY,
    ) -> PositionTimeSeriesResponse:
        """Build the historical-plus-projected market-value series for an account.

        Args:
            account_name: The account identifier.
            projection_date: The date to project forward to. Must be strictly later than the
                resolved start date. No upper bound is enforced — a future date is the point.
            returns: Zero or more requested return names (see
                app.services.projection_returns.SUPPORTED_PROJECTION_RETURNS). Zero returns is
                valid and returns the historical series alone.
            start: Caller-supplied start date, or None to default to the account's own most
                recently recorded position-ladder date.
            periodicity: Calendar aggregation interval, applied independently to the historical
                series and to each projected series. Defaults to per-business-day.

        Returns:
            Populated PositionTimeSeriesResponse — its `position` field carries a series label
            ("Historical" or a requested return's own name), not a position name.

        Raises:
            UnsupportedAttributeError: If any requested return name is unsupported.
            AccountNotFoundError: If the account has no ingested resource at all.
            PositionLadderNotIngestedError: If the account is known but has no ingested
                position ladder.
            MissingRequiredSourceError: If the resolved start precedes the ladder's own
                earliest recorded date.
            InvalidProjectionRangeError: If projection_date is not strictly later than the
                resolved start date.
        """
        log = logger.bind(account_name=account_name, requested_returns=returns)
        projection_returns.validate_returns(returns)

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
            raise PositionLadderNotIngestedError(account_name=account_name)

        ladder_range = summary.position_ladder
        resolved_start = self._resolve_start(account_name, start, ladder_range)

        if projection_date <= resolved_start:
            raise InvalidProjectionRangeError(start=resolved_start, projection_date=projection_date)

        ladder_df = self._ladder_repo.read_full_df(account_name)

        historical_df = self._build_historical_series(
            ladder_df, ladder_range.from_date, resolved_start, periodicity
        )
        start_market_value = float(historical_df.iloc[-1]["market_value"])

        entries: list[PositionTimeSeriesEntry] = [
            PositionTimeSeriesEntry(
                date=row["date"],
                position=_HISTORICAL_LABEL,
                **{"market_value": float(row["market_value"])},
            )
            for _, row in historical_df.iterrows()
        ]

        if returns:
            measures_df = compute_performance_measures(
                compute_daily_portfolio_return(
                    ladder_df, from_date=ladder_range.from_date, through_date=resolved_start
                )
            )
            measures_row = measures_df.loc[measures_df["date"] == resolved_start].iloc[0]
            for return_name in returns:
                annualized_return = measures_row[return_name]
                if pd.isna(annualized_return):
                    continue  # insufficient history — silently omitted (FR-011)
                projected_df = self._build_projected_series(
                    start_market_value,
                    annualized_return,
                    resolved_start,
                    projection_date,
                    periodicity,
                )
                entries.extend(
                    PositionTimeSeriesEntry(
                        date=row["date"],
                        position=return_name,
                        **{"market_value": float(row["market_value"])},
                    )
                    for _, row in projected_df.iterrows()
                )

        entries.sort(key=lambda e: (e.date, e.position))
        response_positions = sorted({entry.position for entry in entries})

        log.info(
            "projection_request",
            resolved_start=str(resolved_start),
            projection_date=str(projection_date),
            periodicity=periodicity.value,
            computed_returns=[p for p in response_positions if p != _HISTORICAL_LABEL],
            row_count=len(entries),
        )

        return PositionTimeSeriesResponse(
            account_name=account_name,
            attributes=["market_value"],
            positions=response_positions,
            from_date=ladder_range.from_date,
            to_date=projection_date,
            periodicity=periodicity,
            entries=entries,
            _links={
                "self": f"/v1/accounts/{account_name}/projection",
                "accounts": "/v1/accounts",
            },
        )

    def _resolve_start(
        self, account_name: str, raw_start: date | None, ladder_range: AccountResourceRange
    ) -> date:
        """Resolve the raw `start` input into a concrete, business-day-aligned date.

        Unlike TimeseriesDateResolver, an omitted start defaults to the ladder's own most
        recently recorded date (not its earliest), and the forward-adjustment is capped at
        that same most-recent date (not at today) — see research.md #3 for why
        TimeseriesDateResolver itself isn't reused here.

        Args:
            account_name: The account identifier (for the error message only).
            raw_start: The caller-supplied start date, or None to default.
            ladder_range: The account's position ladder date range.

        Returns:
            The resolved, business-day-aligned start date.

        Raises:
            MissingRequiredSourceError: If the resolved start precedes the ladder's own
                earliest recorded date.
        """
        start = raw_start if raw_start is not None else ladder_range.to_date
        adjusted: date = pd.bdate_range(start=start, periods=1)[0].date()
        if adjusted > ladder_range.to_date:
            adjusted = pd.bdate_range(end=ladder_range.to_date, periods=1)[0].date()
        if adjusted < ladder_range.from_date:
            raise MissingRequiredSourceError(
                account_name=account_name,
                attribute="market_value",
                source="position_ladder",
                message=(
                    f"position_ladder for account '{account_name}' has no data before "
                    f"{ladder_range.from_date}, but the resolved start date is {adjusted}."
                ),
            )
        return adjusted

    def _build_historical_series(
        self,
        ladder_df: pd.DataFrame,
        from_date: date,
        resolved_start: date,
        periodicity: Periodicity,
    ) -> pd.DataFrame:
        """Build the account-level market_value series through the resolved start date.

        Mirrors TimeSeriesService.get_series's own market_value aggregation exactly
        (research.md #4), so the two are provably numerically identical for the same range.

        Args:
            ladder_df: The account's full position ladder.
            from_date: The ladder's own earliest recorded date.
            resolved_start: The resolved start date (historical range's end, inclusive).
            periodicity: Calendar aggregation interval.

        Returns:
            DataFrame with columns [date, market_value], at least one row, sorted by date.
        """
        aggregated = ladder_df.groupby("date", as_index=False)["market_value"].sum()
        expanded = expand_business_days(aggregated, ["market_value"], from_date, resolved_start)
        return aggregate_last_observation(expanded, periodicity, from_date)

    def _build_projected_series(
        self,
        start_market_value: float,
        annualized_return: float,
        resolved_start: date,
        projection_date: date,
        periodicity: Periodicity,
    ) -> pd.DataFrame:
        """Compound a return's own annualized rate forward from the start date's market value.

        daily_rate = (1 + annualized_return) ** (1 / 260) - 1; V(t) = start_market_value *
        (1 + daily_rate) ** t, t = business days elapsed since resolved_start (research.md
        #5). This is the exact inverse of how `performance_metrics.py` itself annualizes a
        return (`itd_ann = (1 + itd) ** (260 / elapsed) - 1`) — de-annualizing back down to a
        single business day is the 260th root, not a multiplication by sqrt(260) (that factor
        scales *volatility*, not a return, and was the source of a since-fixed defect: it
        produced a ~390% "daily rate" for a 24% annualized return instead of ~0.08%).

        Args:
            start_market_value: The historical series' own final market_value.
            annualized_return: The return's annualized rate as of resolved_start.
            resolved_start: First date of the projected series (t=0).
            projection_date: Last date of the projected series.
            periodicity: Calendar aggregation interval.

        Returns:
            DataFrame with columns [date, market_value], bucketed at the requested periodicity.
        """
        daily_rate = (1 + annualized_return) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
        business_days = pd.bdate_range(start=resolved_start, end=projection_date)
        daily_df = pd.DataFrame(
            {
                "date": [d.date() for d in business_days],
                "market_value": [
                    start_market_value * (1 + daily_rate) ** t for t in range(len(business_days))
                ],
            }
        )
        return aggregate_last_observation(daily_df, periodicity, resolved_start)
