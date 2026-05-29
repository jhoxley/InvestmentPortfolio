from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    date: date
    close: float = Field(gt=0.0)
    fx_rate: float | None = None


class PriceResponse(BaseModel):
    ticker: str
    price: float = Field(gt=0.0)
    currency: str
    timestamp: datetime
    market_status: Literal["open", "closed"]
    as_of_date: date
    fx_rate: float | None = None


class FxRateEntry(BaseModel):
    date: date
    rate: float = Field(gt=0.0)


class FxHistoryResponse(BaseModel):
    pair: str
    base_currency: str
    quote_currency: str
    rates: list[FxRateEntry]


class PriceHistoryResponse(BaseModel):
    ticker: str
    currency: str
    prices: list[PricePoint]


class TickerResolutionResponse(BaseModel):
    identifier: str
    identifier_type: str
    ticker: str
    security_name: str
    exchange: str


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class CacheDeleteResponse(BaseModel):
    ticker: str
    deleted: bool


class CacheClearResponse(BaseModel):
    deleted_count: int
