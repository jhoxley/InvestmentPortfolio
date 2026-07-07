"""Pydantic response models for the position ladder API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Links(BaseModel):
    """HATEOAS links included in every ladder response."""

    model_config = ConfigDict(populate_by_name=True)

    self_: str = Field(alias="self", description="URL of the ladder summary resource")
    download: str = Field(description="URL to download the full XLSX position ladder")


class IngestionSummary(BaseModel):
    """Response body for POST /v1/accounts/{name}/ladder (201 Created or 200 OK)."""

    account_name: str = Field(description="Case-sensitive account identifier")
    status: Literal["created", "refreshed"] = Field(
        description=(
            "'created' for a brand-new ladder; 'refreshed' when the checksum matched an "
            "existing ladder but price/market_value/portfolio_weight were recomputed via "
            "fresh market-data-service calls (rows and date range are not re-expanded)"
        )
    )
    row_count: int = Field(ge=0, description="Total rows in the stored position ladder")
    from_date: date = Field(description="Earliest date in the ladder")
    to_date: date = Field(description="Latest date in the ladder")
    sub_accounts: list[str] = Field(description="Distinct sub-account names present")
    ingested_at: datetime = Field(description="UTC timestamp of the last successful ingestion")
    links: Links = Field(alias="_links", description="HATEOAS navigation links")

    model_config = ConfigDict(populate_by_name=True)


class LadderSummary(BaseModel):
    """Response body for GET /v1/accounts/{name}/ladder."""

    account_name: str = Field(description="Case-sensitive account identifier")
    row_count: int = Field(ge=0, description="Total rows in the stored position ladder")
    from_date: date = Field(description="Earliest date in the ladder")
    to_date: date = Field(description="Latest date in the ladder")
    sub_accounts: list[str] = Field(description="Distinct sub-account names present")
    ingested_at: datetime = Field(description="UTC timestamp of the last successful ingestion")
    links: Links = Field(alias="_links", description="HATEOAS navigation links")

    model_config = ConfigDict(populate_by_name=True)


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details error response body."""

    type: str = Field(description="URI reference identifying the error type")
    title: str = Field(description="Short human-readable summary of the error")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Full human-readable explanation of the error")
    instance: str = Field(description="Request path that triggered the error")
