# Quickstart: Price Series Gap Fill

**Branch**: `006-price-series-fill` | **Date**: 2026-05-17

---

## Overview

After this feature is implemented, all `/securities/{ticker}/history` and `/fx/{pair}/history` responses are guaranteed to contain an entry for every Mon–Fri business day in the requested range. Missing trading days (holidays, data outages, stale data) are filled by carrying the nearest observed price forward (or backward for the start of range).

---

## Scenario 1 — Forward-Fill Mid-Series Gap (US1)

**What to observe**: A date range spanning a market holiday returns an entry for the holiday date, carrying the pre-holiday price.

New Year's Day 2025 fell on Wednesday 1 Jan. The NYSE was closed. 2 Jan (Thursday) was the first trading day of the year.

```bash
curl "http://localhost:8000/securities/AAPL/history?from=2024-12-31&to=2025-01-06"
```

**Expected result**: 5 entries (Tue 31 Dec, Wed 1 Jan, Thu 2 Jan, Fri 3 Jan, Mon 6 Jan). The entry for 2025-01-01 carries the same close price as 2024-12-31.

```json
{
  "ticker": "AAPL",
  "currency": "USD",
  "prices": [
    { "date": "2024-12-31", "close": 250.00 },
    { "date": "2025-01-01", "close": 250.00 },
    { "date": "2025-01-02", "close": 243.08 },
    { "date": "2025-01-03", "close": 243.31 },
    { "date": "2025-01-06", "close": 252.10 }
  ]
}
```

*Prices above are illustrative; actual values depend on live data.*

---

## Scenario 2 — Back-Fill from Requested Start Date (US2)

**What to observe**: A start date before any available observation still returns entries from the requested start date.

Request a range starting on 1 Jan 2025 (holiday, no observation) when the first observation is 2 Jan 2025:

```bash
curl "http://localhost:8000/securities/AAPL/history?from=2025-01-01&to=2025-01-03"
```

**Expected result**: 3 entries (1 Jan, 2 Jan, 3 Jan). The entry for 2025-01-01 carries the 2 Jan price (back-filled).

```json
{
  "ticker": "AAPL",
  "currency": "USD",
  "prices": [
    { "date": "2025-01-01", "close": 243.08 },
    { "date": "2025-01-02", "close": 243.08 },
    { "date": "2025-01-03", "close": 243.31 }
  ]
}
```

---

## Scenario 3 — Fill Forward to Today (US3)

**What to observe**: A request with no `to` parameter (defaults to today) returns an entry for today even when yfinance's last observation is T-1.

```bash
curl "http://localhost:8000/securities/AAPL/history?from=2025-05-14"
```

**Expected result**: Today's date appears in the response, carrying yesterday's close price if today's data isn't yet available.

---

## Scenario 4 — FX History Gap-Fill (FR-009)

**What to observe**: The FX endpoint also returns a complete Mon-Fri series.

```bash
curl "http://localhost:8000/fx/GBPUSD/history?from=2024-12-31&to=2025-01-06"
```

**Expected result**: 5 entries (31 Dec, 1 Jan, 2 Jan, 3 Jan, 6 Jan). The 1 Jan entry carries the 31 Dec rate.

---

## Scenario 5 — Currency Conversion With No FX Spikes (SC-005)

**What to observe**: Requesting history in GBP for a USD security across a holiday period produces no artificial spikes — the converted price is smooth on holiday dates despite the underlying FX rate having a gap.

```bash
curl "http://localhost:8000/securities/AAPL/history?from=2024-12-31&to=2025-01-06&currency=GBP"
```

**Expected result**: Each entry's close price is the USD price × the GBP/USD rate for that specific date. Holiday dates use a gap-filled FX rate, so no spike or zero appears. The series is smooth across the holiday.

---

## Verifying BDD Test Coverage

Run just the gap-fill scenarios:

```bash
pytest tests/steps/price_gap_fill_steps.py tests/steps/fx_gap_fill_steps.py tests/steps/gap_fill_fx_conversion_steps.py -v
```

Run the full suite (must remain green with no regressions):

```bash
pytest -v
```

---

## Edge Cases to Verify Manually

| Edge Case | Command | Expected |
|-----------|---------|----------|
| Weekend start/end | `?from=2025-01-04&to=2025-01-05` (Sat-Sun) | Empty `prices` list |
| Single day (trading) | `?from=2025-01-02&to=2025-01-02` | 1 entry |
| Single day (holiday) | `?from=2025-01-01&to=2025-01-01` | 0 entries (single holiday, no observations, 404) |
| Future end date | `?from=2025-01-02&to=2099-12-31` | Last known price forward-filled to all future Mon-Fri |
