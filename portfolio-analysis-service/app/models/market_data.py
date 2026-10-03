"""Pydantic models for market-data-service integration."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class IdentifierMappingEntry(BaseModel):
    """One entry in the configured sub-account-to-identifier mapping file."""

    name: str = Field(description="Sub-account name, matched exactly against the ladder")
    isin: str | None = Field(default=None, description="Fallback identifier, used if no ticker")
    ticker: str | None = Field(default=None, description="Preferred identifier when populated")
    var_proxy: str | None = Field(
        default=None,
        description="Identifier whose returns stand in for this instrument's VaR scenarios",
    )
    var_proxy_mode: Literal["fill_gaps", "always"] = Field(
        default="fill_gaps",
        description="fill_gaps: proxy only where this instrument has no return. "
        "always: proxy for every scenario day in the window.",
    )
    var_proxy_scale: float = Field(
        default=1.0, gt=0, description="Static multiplier applied to the proxy's returns"
    )


class PriceHistoryPoint(BaseModel):
    """A single date/close pair returned by the market-data-service."""

    date: dt.date = Field(description="Trading/calendar date")
    close: float = Field(description="Price in the requested currency")


class ObservedPriceHistory(BaseModel):
    """Observed-only (never gap-filled) price history for one identifier.

    Returned by MarketDataClient.get_observed_price_history(). `first_observed_date` and
    `last_observed_date` cover the instrument's whole known history (not just the requested
    range) and are None when market-data-service does not support observed-only history
    (feature 009) or knows nothing about the identifier.
    """

    points: list[PriceHistoryPoint] = Field(
        description="Only dates with a real observation; never forward- or back-filled"
    )
    first_observed_date: dt.date | None = Field(
        default=None, description="Earliest date market-data-service has ever observed a price"
    )
    last_observed_date: dt.date | None = Field(
        default=None, description="Latest date market-data-service has ever observed a price"
    )
