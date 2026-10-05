"""Typed response shapes for portfolio-analysis-service (no calculation logic).

Field names/shapes mirror portfolio-analysis-service's own
`app/models/timeseries.py` and its `/specs/004-account-timeseries-api`
OpenAPI contract, verified against source rather than assumed.
"""

from __future__ import annotations

import datetime as dt
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountResourceRange(BaseModel):
    """Earliest/latest available date for one ingested resource."""

    from_date: date
    to_date: date


class AccountSummary(BaseModel):
    """One entry in GET /v1/accounts's `accounts` array."""

    account_name: str
    capital_ledger: AccountResourceRange | None = None
    position_ladder: AccountResourceRange | None = None


class AttributeDefinition(BaseModel):
    """One entry in GET /v1/timeseries/attributes's `attributes` array."""

    name: str
    description: str
    source: str


class TimeSeriesEntry(BaseModel):
    """One row of a timeseries response: a date plus dynamic attribute values.

    Only `date` is declared; requested attribute values (e.g. `market_value`)
    arrive as extra keys via `extra="allow"`, mirroring the service's own
    `TimeSeriesEntry` model.
    """

    model_config = ConfigDict(extra="allow")

    date: date


class TimeSeriesResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/timeseries."""

    account_name: str
    attributes: list[str]
    from_date: date
    to_date: date
    # Echoed by the service from its feature 008 onward. Optional so a response
    # from an older service still validates — the client warns when it is absent
    # or differs from what was requested (021 research.md #6).
    periodicity: str | None = None
    entries: list[TimeSeriesEntry]
    links: dict[str, str] = Field(default_factory=dict)


class PositionSummary(BaseModel):
    """One entry in GET /v1/accounts/{account_name}/positions's `positions` array."""

    position: str
    from_date: date
    to_date: date


class PositionsResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/positions."""

    account_name: str
    positions: list[PositionSummary]
    links: dict[str, str] = Field(default_factory=dict)


class PositionTimeSeriesEntry(BaseModel):
    """One row of a position timeseries response: a date, a position, plus dynamic attribute values.

    Only `date` and `position` are declared; requested attribute values
    (e.g. `market_value`) arrive as extra keys via `extra="allow"`, mirroring
    `TimeSeriesEntry`.
    """

    model_config = ConfigDict(extra="allow")

    date: date
    position: str


class PositionTimeSeriesResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/position."""

    account_name: str
    attributes: list[str]
    positions: list[str]
    from_date: date
    to_date: date
    # See TimeSeriesResponse.periodicity.
    periodicity: str | None = None
    entries: list[PositionTimeSeriesEntry]
    links: dict[str, str] = Field(default_factory=dict)


class StdDevBand(BaseModel):
    """One standard deviation band around the mean, in basis points.

    Not rendered by the Risk page (spec 024 explicitly excludes this from its
    statistics table) — modeled here only because it is a required nested
    field of HistogramStatistics and must validate.
    """

    sigma: int
    multiple: float
    lower: float
    upper: float


class HistogramStatistics(BaseModel):
    """Summary statistics of an account's rounded basis-point return observations.

    Scalar fields are None when there are too few observations to define them
    (see portfolio-analysis-service/app/models/risk.py, verified against source).
    """

    count: int
    mean: float | None
    median: float | None
    mode: int | None
    minimum: int | None
    maximum: int | None
    std_dev: float | None
    std_dev_bands: list[StdDevBand]
    skewness: float | None
    kurtosis: float | None


class ReturnHistogramResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/risk/return-histogram."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    from_date: date
    to_date: date
    histogram: list[tuple[int, int]]
    statistics: HistogramStatistics
    links: dict[str, str] = Field(default_factory=dict, alias="_links")


# --- 026-var-risk-view: client-side mirrors of portfolio-analysis-service's 012/013
# response shapes (specs/012-var-calculation-runs, specs/013-var-series-backtest-api).


class DateRange(BaseModel):
    """An inclusive from/to date range."""

    from_date: date
    to_date: date


class VarStatusSummary(BaseModel):
    """A deliberate subset of 012's VarStatus: only what this view needs.

    Extra fields the full VarStatus response carries (stale_dates_last_run,
    pending_outcomes, last_run, instruments, warnings) are not modeled here and are
    silently ignored by Pydantic's default `extra="ignore"` behaviour.
    """

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    computed_range: DateRange | None = None
    missing_dates: int
    links: dict[str, str] = Field(default_factory=dict, alias="_links")


class ConfidenceLevelEstimate(BaseModel):
    """One confidence level's VaR/ES and exception flags for a VarSeriesEntry."""

    confidence_bp: int
    var_gbp: float | None
    var_pct: float | None
    es_gbp: float | None
    es_pct: float | None
    hypothetical_exception: bool | None
    ladder_exception: bool | None


class VarSeriesEntry(BaseModel):
    """One business date's previously computed VaR estimate joined with its outcome."""

    date: dt.date
    outcome_date: dt.date
    total_value_gbp: float
    scenario_count: int
    actual_mv_pct: float
    proxied_mv_pct: float
    rescaled_mv_pct: float
    quality: Literal["ok", "degraded", "insufficient"]
    quality_reason: str | None
    hypothetical_pnl_gbp: float | None
    ladder_pnl_gbp: float | None
    levels: list[ConfidenceLevelEstimate] = Field(default_factory=list)


class VarSeriesResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/risk/var."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    lookback_code: str
    lookback_days: int
    from_date: date
    to_date: date
    series: list[VarSeriesEntry] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict, alias="_links")


class RollingExceptionPoint(BaseModel):
    """One point of the optional 250-day rolling exception count series."""

    date: dt.date
    exception_count: int


class BacktestConfidenceResult(BaseModel):
    """One confidence level's backtest statistics over the requested observation set."""

    confidence_bp: int
    observation_count: int
    exception_count: int
    expected_exceptions: float | None
    exception_rate: float | None
    kupiec_lr: float | None
    kupiec_p_value: float | None
    christoffersen_independence_lr: float | None
    christoffersen_independence_p_value: float | None
    conditional_coverage_lr: float | None
    conditional_coverage_p_value: float | None
    zone: Literal["green", "yellow", "red"] | None
    exception_dates: list[date] = Field(default_factory=list)
    mean_var_gbp: float | None
    var_stability: float | None
    rolling_exceptions: list[RollingExceptionPoint] | None = None


class VarBacktestResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/risk/var/backtest."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    lookback_code: str
    lookback_days: int
    from_date: date
    to_date: date
    pnl_basis: Literal["hypothetical", "ladder"]
    min_quality: Literal["ok", "degraded"]
    levels: list[BacktestConfidenceResult] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict, alias="_links")


class MethodLookback(BaseModel):
    """One configured look-back's code, business-day length, and headline status."""

    code: str
    business_days: int
    is_headline: bool


class VarMethodsResponse(BaseModel):
    """Response body for GET /v1/risk/var/methods."""

    model_config = ConfigDict(populate_by_name=True)

    method: str
    methodology_version: str
    lookbacks: list[MethodLookback] = Field(default_factory=list)
    confidence_levels_bp: list[int] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict, alias="_links")
