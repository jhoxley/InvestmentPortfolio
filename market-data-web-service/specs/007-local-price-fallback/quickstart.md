# Quickstart: Local Price File Fallback

**Feature**: 007-local-price-fallback  
**Date**: 2026-05-20

This document describes the end-to-end integration scenarios that BDD tests must cover, and serves as a guide for manual verification during development.

---

## Setup Prerequisites

1. A fallback configuration JSON file (e.g., `test_fallback_config.json`) with at least one entry.
2. A CSV price file referenced by the config.
3. `Settings.fallback.config_path` pointing to the config file (set in `config.yaml` or via `dependency_overrides` in tests).

---

## Scenario 1: Price History from Local File (YFinance returns no data)

**Config**:
```json
{
  "PRIV01": {
    "csv_path": "tests/fixtures/priv01_prices.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Close",
    "use_local_only": false
  }
}
```

**CSV** (`priv01_prices.csv`):
```
Date,Close
2025-01-02,100.00
2025-01-06,110.00
```

**Request**:
```
GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-06
```

**Expected response** (200):
```json
{
  "ticker": "PRIV01",
  "currency": "GBP",
  "prices": [
    {"date": "2025-01-02", "close": 100.00},
    {"date": "2025-01-03", "close": 100.00},
    {"date": "2025-01-06", "close": 110.00}
  ]
}
```

**Key assertions**:
- Response status 200.
- 3 entries for the Mon–Fri range (2025-01-04 and 2025-01-05 are Saturday/Sunday, skipped).
- 2025-01-03 is filled by forward-carry from 2025-01-02 (100.00).
- Currency is "GBP" as declared in config.
- YFinance was never called (verified by mock assertion in test).

---

## Scenario 2: Current Price from Local File

**Config**: same as Scenario 1.

**Request**:
```
GET /securities/PRIV01/price
```

**Expected response** (200):
```json
{
  "ticker": "PRIV01",
  "price": 110.00,
  "currency": "GBP",
  "market_status": "closed",
  "as_of_date": "2025-01-06"
}
```

**Key assertions**:
- Price is the most recent entry in the CSV (2025-01-06).
- `market_status` is always `"closed"` for local file data.

---

## Scenario 3: Unknown Ticker with No Fallback → 404

**Config**: no entry for `"UNKNOWN"`.

**Request**:
```
GET /securities/UNKNOWN/history?from=2025-01-02&to=2025-01-06
```

**Expected response** (404):
```json
{"detail": "No valid price data found for ticker 'UNKNOWN'"}
```

---

## Scenario 4: ISIN Pseudo-Ticker via Identifier Resolution

**Config**:
```json
{
  "GB00B0PRVT01": {
    "csv_path": "tests/fixtures/priv_isin_prices.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Close",
    "use_local_only": true
  }
}
```

**Step 1 — Resolve identifier**:
```
GET /identifiers/GB00B0PRVT01
```

**Expected response** (200):
```json
{
  "identifier": "GB00B0PRVT01",
  "identifier_type": "ISIN",
  "ticker": "GB00B0PRVT01",
  "security_name": "",
  "exchange": ""
}
```

**Step 2 — Use pseudo-ticker for pricing** (direct, no resolution step required):
```
GET /securities/GB00B0PRVT01/history?from=2025-01-02&to=2025-01-02
```

**Expected response** (200) — prices from the local file, in GBP.

---

## Scenario 5: use_local_only Bypasses YFinance

**Config**:
```json
{
  "PRIV01": {
    "csv_path": "tests/fixtures/priv01_prices.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Close",
    "use_local_only": true
  }
}
```

**Request**:
```
GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-02
```

**Key assertions**:
- Response is 200 with prices from the local file.
- YFinance provider's `get_price_history` was never called (mock assertion).

---

## Scenario 6: FX Conversion Applied to Local File Prices

**Config**: `PRIV01` with `currency: "GBP"`.

**Request**:
```
GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-02&currency=USD
```

Assumes GBPUSD FX rate for 2025-01-02 is 1.25 (mocked in test).

**Expected response** (200):
```json
{
  "ticker": "PRIV01",
  "currency": "USD",
  "prices": [
    {"date": "2025-01-02", "close": 125.00, "fx_rate": 1.25}
  ]
}
```

**Key assertions**:
- Price is the local file price (100.00) × GBPUSD rate (1.25) = 125.00.
- The FX conversion path is identical to the primary-source path.

---

## Scenario 7: Missing Fallback File → 503

**Config**:
```json
{
  "PRIV01": {
    "csv_path": "/nonexistent/path/priv01.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Close"
  }
}
```

**Request**:
```
GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-06
```

**Expected response** (503):
```json
{"detail": "Fallback CSV file not found: /nonexistent/path/priv01.csv"}
```

---

## Scenario 8: Empty Fallback File → 404

**Config**: `PRIV01` pointing to a CSV file with headers only (no data rows).

**Request**:
```
GET /securities/PRIV01/history?from=2025-01-02&to=2025-01-06
```

**Expected response** (404) — treated as no data available.

---

## Test Fixture Files Needed

| File | Content |
|------|---------|
| `tests/fixtures/priv01_prices.csv` | Two rows: 2025-01-02 at 100.00 and 2025-01-06 at 110.00 |
| `tests/fixtures/priv_isin_prices.csv` | One row: 2025-01-02 at 150.00 |
| `tests/fixtures/priv01_empty.csv` | Headers only: `Date,Close` |
| `tests/fixtures/fallback_config.json` | Config pointing to the above files |
| `tests/fixtures/fallback_config_local_only.json` | Config with `use_local_only: true` |
| `tests/fixtures/fallback_config_missing_file.json` | Config with a non-existent csv_path |
