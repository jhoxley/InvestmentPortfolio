# Data Model: Security Pricing API

**Feature**: 001-security-pricing-api
**Date**: 2026-05-04

---

## Entities

### Security

Represents a financial instrument identified by a Yahoo Finance ticker symbol.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| ticker | str | Yahoo Finance ticker (e.g. `AAPL`, `VOD.L`) | Non-empty; URL-safe characters only |
| currency | str | ISO 4217 currency code (e.g. `USD`, `GBp`) | Non-empty string from yfinance |
| exchange | str | Exchange name (e.g. `NASDAQ`, `LSE`) | Informational; sourced from yfinance |

> Security is not persisted. It is resolved dynamically from yfinance on each request.

---

### PricePoint

A single price observation at a specific point in time.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| date | date | Trading date (YYYY-MM-DD) | Valid calendar date; not in future |
| close | float | Closing price for that date | Must be > 0.0 |

---

### PriceResponse *(API response model)*

Returned by `GET /securities/{ticker}/price`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | str | ✅ | Requested ticker symbol |
| price | float | ✅ | Current or most recent close price (always > 0) |
| currency | str | ✅ | ISO 4217 currency code |
| timestamp | datetime | ✅ | ISO 8601 datetime of the price observation |
| market_status | str | ✅ | `"open"` or `"closed"` |

---

### PriceHistoryResponse *(API response model)*

Returned by `GET /securities/{ticker}/history`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | str | ✅ | Requested ticker symbol |
| currency | str | ✅ | ISO 4217 currency code |
| prices | list[PricePoint] | ✅ | Chronologically ascending list of daily close prices |

---

### ErrorResponse *(API error model)*

Returned on 404, 422, and 503 responses.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| detail | str | ✅ | Human-readable error description |
| code | str | ❌ | Optional machine-readable error code |

---

## Validation Rules

- **Price positivity**: Any price value (current or historical) equal to zero or negative MUST be treated as data unavailability and rejected.
- **Ticker format**: Tickers are passed as URL path segments. They must be non-empty strings. Special characters that cannot appear in a URL path (e.g. `$`, `#`) are rejected at the HTTP layer with a 422 response.
- **Date range**: When `from` > `to`, the API returns 422 immediately without calling yfinance.
- **Empty history**: If yfinance returns data but all prices are zero or null, treat as 404 (no valid data).

---

## Internal Module Boundaries (SOLID — SRP)

| Module | Responsibility |
|--------|----------------|
| `app/models/pricing.py` | Pydantic schemas for all request/response types |
| `app/providers/yfinance_provider.py` | All yfinance calls; returns raw data or raises provider-specific exceptions |
| `app/services/pricing_service.py` | Business logic: validates prices, maps provider data to response models, handles zero-price filtering |
| `app/api/securities.py` | FastAPI router; HTTP layer only — no business logic; injects PricingService via dependency injection |
| `app/logging_config.py` | structlog configuration and JSON log setup |
| `app/main.py` | FastAPI app instantiation, router registration, lifespan events |

Dependencies flow in one direction: `api → service → provider`. No circular dependencies.
