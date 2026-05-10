from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    date: date
    close: float = Field(gt=0.0)


class PriceResponse(BaseModel):
    ticker: str
    price: float = Field(gt=0.0)
    currency: str
    timestamp: datetime
    market_status: Literal["open", "closed"]
    as_of_date: date


class PriceHistoryResponse(BaseModel):
    ticker: str
    currency: str
    prices: list[PricePoint]


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class CacheDeleteResponse(BaseModel):
    ticker: str
    deleted: bool


class CacheClearResponse(BaseModel):
    deleted_count: int
