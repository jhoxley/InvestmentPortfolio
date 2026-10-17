"""Pydantic models for the VaR series, backtest and methods read API (feature 013).

Kept separate from app/models/var.py, which describes the run/status write-side
resources (feature 012); these describe this feature's distinct read-side resources,
built by joining and summarising feature 012's existing estimates/outcomes store.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PnlBasis = Literal["hypothetical", "ladder"]
MinQuality = Literal["ok", "degraded"]
TrafficLightZone = Literal["green", "yellow", "red"]
Quality = Literal["ok", "degraded", "insufficient"]


class ConfidenceLevelEstimate(BaseModel):
    """One confidence level's VaR/ES and exception flags for a single series entry."""

    confidence_bp: int
    var_gbp: float | None
    var_pct: float | None
    es_gbp: float | None
    es_pct: float | None
    hypothetical_exception: bool | None
    ladder_exception: bool | None


class VarSeriesEntry(BaseModel):
    """One business date's previously computed estimate joined with its realised outcome."""

    date: dt.date
    outcome_date: dt.date
    total_value_gbp: float
    scenario_count: int
    actual_mv_pct: float
    proxied_mv_pct: float
    rescaled_mv_pct: float
    quality: Quality
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
    from_date: dt.date
    to_date: dt.date
    series: list[VarSeriesEntry] = Field(default_factory=list)
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


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
    zone: TrafficLightZone | None
    exception_dates: list[dt.date] = Field(default_factory=list)
    mean_var_gbp: float | None
    var_stability: float | None
    rolling_exceptions: list[RollingExceptionPoint] | None = None


class VarBacktestResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/risk/var/backtest."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str
    lookback_code: str
    lookback_days: int
    from_date: dt.date
    to_date: dt.date
    pnl_basis: PnlBasis
    min_quality: MinQuality
    levels: list[BacktestConfidenceResult] = Field(default_factory=list)
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


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
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")
