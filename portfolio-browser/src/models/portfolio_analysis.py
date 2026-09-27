"""Typed response shapes for portfolio-analysis-service (no calculation logic).

Field names/shapes mirror portfolio-analysis-service's own
`app/models/timeseries.py` and its `/specs/004-account-timeseries-api`
OpenAPI contract, verified against source rather than assumed.
"""

from __future__ import annotations

from datetime import date

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
