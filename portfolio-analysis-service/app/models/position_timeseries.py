"""Pydantic response models for the position time series API."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PositionSummary(BaseModel):
    """One entry in the positions-enumeration endpoint's response."""

    position: str = Field(description="Position name, aliased from the ladder's sub_account")
    from_date: date = Field(description="Earliest recorded date for this position")
    to_date: date = Field(description="Latest recorded date for this position")


class PositionsResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/positions."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str = Field(description="Case-sensitive account identifier")
    positions: list[PositionSummary] = Field(
        description="Every distinct position recorded for the account, sorted by name"
    )
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


class PositionTimeSeriesEntry(BaseModel):
    """One row of the position time series response.

    Only `date` and `position` are declared; requested attribute values (e.g.
    `market_value`, `quantity`) are set dynamically per entry via `extra="allow"`, so a
    response never carries null/missing keys for attributes that weren't requested.
    """

    model_config = ConfigDict(extra="allow")

    date: date
    position: str


class PositionTimeSeriesResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/position."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str = Field(description="Case-sensitive account identifier")
    attributes: list[str] = Field(description="Requested attribute names, in request order")
    positions: list[str] = Field(description="Positions actually represented in entries, sorted")
    from_date: date = Field(description="Resolved start date of the time series")
    to_date: date = Field(description="Resolved end date of the time series")
    entries: list[PositionTimeSeriesEntry] = Field(
        description="One entry per (date, position) combination that has data"
    )
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")
