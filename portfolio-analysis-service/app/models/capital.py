"""Pydantic response models for the capital ledger API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.ladder import Links


class CapitalIngestionSummary(BaseModel):
    """Response body for POST /v1/accounts/{name}/capital (201 Created or 200 OK)."""

    account_name: str = Field(description="Case-sensitive account identifier")
    status: Literal["created", "refreshed"] = Field(
        description=(
            "'created' for a brand-new capital ledger; 'refreshed' when the checksum matched "
            "an existing ledger — no recomputation occurs since this resource has no "
            "enrichment step, only the ingested_at timestamp is updated"
        )
    )
    row_count: int = Field(ge=0, description="Total rows in the stored capital ledger")
    from_date: date = Field(description="Earliest date in the capital ledger")
    to_date: date = Field(description="Latest date in the capital ledger")
    ingested_at: datetime = Field(description="UTC timestamp of the last successful ingestion")
    links: Links = Field(alias="_links", description="HATEOAS navigation links")

    model_config = ConfigDict(populate_by_name=True)


class CapitalSummary(BaseModel):
    """Response body for GET /v1/accounts/{name}/capital."""

    account_name: str = Field(description="Case-sensitive account identifier")
    row_count: int = Field(ge=0, description="Total rows in the stored capital ledger")
    from_date: date = Field(description="Earliest date in the capital ledger")
    to_date: date = Field(description="Latest date in the capital ledger")
    ingested_at: datetime = Field(description="UTC timestamp of the last successful ingestion")
    links: Links = Field(alias="_links", description="HATEOAS navigation links")

    model_config = ConfigDict(populate_by_name=True)
