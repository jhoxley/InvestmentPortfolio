"""Pydantic models for market-data-service integration."""

import datetime as dt

from pydantic import BaseModel, Field


class IdentifierMappingEntry(BaseModel):
    """One entry in the configured sub-account-to-identifier mapping file."""

    name: str = Field(description="Sub-account name, matched exactly against the ladder")
    isin: str | None = Field(default=None, description="Fallback identifier, used if no ticker")
    ticker: str | None = Field(default=None, description="Preferred identifier when populated")


class PriceHistoryPoint(BaseModel):
    """A single date/close pair returned by the market-data-service."""

    date: dt.date = Field(description="Trading/calendar date")
    close: float = Field(description="Price in the requested currency")
