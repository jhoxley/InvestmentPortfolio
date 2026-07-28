"""Pydantic response models for the account performance API."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PerformanceEntry(BaseModel):
    """One row of a performance response.

    Only the `date` field is declared; requested measure values (e.g. `ITD`, `1Y`) are
    set dynamically per entry via `extra="allow"`, so a response never carries a key for
    a measure that either wasn't requested or isn't yet computable for that date.
    """

    model_config = ConfigDict(extra="allow")

    date: date


class PerformanceResponse(BaseModel):
    """Response body for GET /v1/accounts/{account_name}/performance."""

    model_config = ConfigDict(populate_by_name=True)

    account_name: str = Field(description="Case-sensitive account identifier")
    attributes: list[str] = Field(description="Requested measure names, in request order")
    from_date: date = Field(description="Resolved start date of the performance series")
    to_date: date = Field(description="Resolved end date of the performance series")
    entries: list[PerformanceEntry] = Field(description="One entry per business day")
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")


class PerformanceAttributeDefinition(BaseModel):
    """One entry in the performance attribute metadata endpoint's response."""

    name: str = Field(description="Wire-format measure name")
    description: str = Field(description="Human-readable meaning, including its formula")
    source: str = Field(description="Source ledger this measure is derived from")


class PerformanceAttributeMetadataResponse(BaseModel):
    """Response body for GET /v1/performance/attributes."""

    model_config = ConfigDict(populate_by_name=True)

    attributes: list[PerformanceAttributeDefinition] = Field(
        description="All supported performance measures"
    )
    links: dict[str, str] = Field(alias="_links", description="HATEOAS navigation links")
