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
    entries: list[TimeSeriesEntry]
    links: dict[str, str] = Field(default_factory=dict)
