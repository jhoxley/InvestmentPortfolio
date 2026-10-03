# Quickstart: Observed-Only Price History (`fill=none`)

**Feature**: `specs/009-observed-prices-fill-none` | **Date**: 2026-10-03

How to run, exercise and verify this feature once implemented.

---

## Run the service

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Swagger UI: <http://localhost:8000/docs> — `fill` appears as a dropdown on
`GET /securities/{ticker}/history` with `all` preselected.

---

## Exercise the endpoint

### Default behaviour (unchanged)

```powershell
curl "http://localhost:8000/securities/AAPL/history?from=2025-01-02&to=2025-01-10"
```

Every Mon–Fri in the range has an entry; holiday entries carry the prior price. Byte-identical to the
response before this feature, except for the two additive fields.

### Observed prices only

```powershell
curl "http://localhost:8000/securities/AAPL/history?from=2025-01-02&to=2025-01-10&fill=none"
```

```json
{
  "ticker": "AAPL",
  "currency": "USD",
  "prices": [
    { "date": "2025-01-02", "close": 243.85, "fx_rate": null },
    { "date": "2025-01-06", "close": 245.00, "fx_rate": null }
  ],
  "first_observed_date": "1980-12-12",
  "last_observed_date": "2025-10-02"
}
```

Note the series skips business days with no observation, and the window fields reach well outside the
requested range.

### Observed prices converted to GBP

```powershell
curl "http://localhost:8000/securities/AAPL/history?from=2025-01-02&to=2025-01-10&currency=GBP&fill=none"
```

Same set of dates as the unconverted call; each `close` converted at that date's rate, with `fx_rate`
populated per entry.

### Invalid mode

```powershell
curl -i "http://localhost:8000/securities/AAPL/history?fill=forward"
```

`422`, with `loc: ["query", "fill"]`. No data-source call is made.

---

## Verify the no-earlier-data memory

Pick an instrument with a short trading history and request a window that starts before it exists.

```powershell
# 1. Cold — fetches, caches, and records the boundary
curl "http://localhost:8000/securities/<SHORT-HISTORY-TICKER>/history?from=2015-01-01&to=2025-10-01"

# 2. Repeat — must not call the data source for the pre-history segment
curl "http://localhost:8000/securities/<SHORT-HISTORY-TICKER>/history?from=2010-01-01&to=2025-10-01"
```

Expect the second call to complete in **at most 50% of the first call's elapsed time** (SC-006 — time both
and record the figures), and the two responses to contain the same price entries from the instrument's
first observation onward.

Inspect the sidecar and the logs:

```powershell
Get-Content .\cache\<SHORT-HISTORY-TICKER>.meta.json    # {"no_data_before": "2024-01-02"}
Select-String -Path .\logs\*.log -Pattern "no_earlier_data"
```

Expected structured events, each naming the ticker and the date boundary:

| Event | When |
|---|---|
| `cache_no_earlier_data_recorded` | The service learns nothing exists before a date. |
| `cache_no_earlier_data_skip` | An earlier-segment fetch is suppressed. |
| `cache_no_earlier_data_invalidated` | Earlier data was found, or the boundary was contradicted. |

### Confirm invalidation

```powershell
curl -X DELETE "http://localhost:8000/cache/<SHORT-HISTORY-TICKER>"
Test-Path .\cache\<SHORT-HISTORY-TICKER>.meta.json      # must be False
```

Deleting the cached history must remove the sidecar with it; the next request re-derives both from
whatever the source returns.

---

## Run the tests

```powershell
.venv\Scripts\python -m pytest                                      # full suite
.venv\Scripts\python -m pytest tests/steps/observed_only_history_steps.py
.venv\Scripts\python -m pytest tests/steps/cache_no_earlier_data_steps.py
```

Quality gates:

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy app
```

---

## BDD-first check

Before any implementation task begins, the five new feature files must be present and their scenarios
failing:

```powershell
.venv\Scripts\python -m pytest tests/steps/observed_only_history_steps.py `
                              tests/steps/observation_window_steps.py `
                              tests/steps/cache_no_earlier_data_steps.py `
                              tests/steps/observed_only_fallback_steps.py `
                              tests/steps/observed_only_fx_steps.py
```

All must be RED. Implementation starts only after that is confirmed (constitution III).

---

## Things to watch while verifying

- **`fill=all` must be unchanged.** The whole existing suite passing is the real check (SC-003); run it
  before and after.
- **Empty range now 404s in both modes.** A cached ticker queried over a range it has no rows for
  previously returned 200 with an empty `prices` list; it now returns 404. See the Behaviour Change
  section of `plan.md`.
- **A provider outage must not record a boundary** (FR-028). With the data source unavailable, a request
  that spans before the cached start must return 503 and leave no `.meta.json` behind — and a later
  successful fetch of earlier data must not be suppressed.
- **Other endpoints ignore `fill`** (FR-010). `curl "…/securities/AAPL/price?fill=none"` and
  `curl "…/fx/GBPUSD/history?fill=none"` must return exactly what they return without the parameter.
- **Window fields survive currency conversion.** Compare a `currency=GBP` response against the
  unconverted one — both must report the same `first_observed_date` / `last_observed_date`.
- **Fallback instruments.** For a `use_local_only` entry, `fill=none` returns exactly the CSV rows inside
  the range — no out-of-range rows, no manufactured business days.

---

## Consumer notes (portfolio-analysis-service)

The Value-at-Risk work that motivates this feature should request `fill=none` and compute returns from
consecutive observed dates. `first_observed_date` tells it whether the instrument has enough real history
for the required lookback before any calculation is attempted. Under `fill=all` a flat day is
indistinguishable from a genuine zero-return day, which understates risk — that is the bug this feature
exists to remove.
