"""Pydantic response models for the account time series API."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TimeSeriesEntry(BaseModel):
    """One row of a time series response.

    Only the `date` field is declared; requested attribute values (e.g. `capital`,
    `market_value`) are set dynamically per entry via `extra="allow"`, so a response
    never carries null/missing keys for attributes that weren't requested (FR-015).
    """

    model_config = ConfigDict(extra="allow")

    date: date


class TimeSeriesResponse(BaseModel):
    """Response body for GET /v1/accounts/{name}/timeseries."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str = Field(description="Case-sensitive account identifier")
    attributes: list[str] = Field(description="Requested attribute names, in request order")
    from_date: date = Field(description="Resolved start date of the time series")
    to_date: date = Field(description="Resolved end date of the time series")
    entries: list[TimeSeriesEntry] = Field(description="One entry per business day")
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


class AttributeDefinition(BaseModel):
    """One entry in the attribute metadata endpoint's response."""

    name: str = Field(description="Wire-format attribute name")
    description: str = Field(description="Human-readable meaning")
    source: str = Field(description="Source ledger(s) this attribute is derived from")


class AttributeMetadataResponse(BaseModel):
    """Response body for GET /v1/timeseries/attributes."""

    model_config = ConfigDict(populate_by_name=True)

    attributes: list[AttributeDefinition] = Field(description="All supported attributes")
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


class AccountResourceRange(BaseModel):
    """Earliest/latest available date for one ingested resource."""

    from_date: date = Field(description="Earliest recorded date for this resource")
    to_date: date = Field(description="Latest recorded date for this resource")


class AccountSummary(BaseModel):
    """One entry in the accounts-enumeration endpoint's response."""

    account_name: str = Field(description="Case-sensitive account identifier")
    capital_ledger: AccountResourceRange | None = Field(
        description="Capital ledger date range, or null if not ingested"
    )
    position_ladder: AccountResourceRange | None = Field(
        description="Position ladder date range, or null if not ingested"
    )


class AccountsResponse(BaseModel):
    """Response body for GET /v1/accounts."""

    model_config = ConfigDict(populate_by_name=True)

    accounts: list[AccountSummary] = Field(
        description="Every account with at least one ingested resource"
    )
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")
