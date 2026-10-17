# Baseline: before feature 009 (observed-only price history)

**Recorded**: 2026-10-03 | **Task**: T001
**Purpose**: Reference for the SC-003 regression check in T040 — every one of these pre-existing tests
must still pass after the feature lands.

## Test suite

```
.venv\Scripts\python -m pytest -q
→ 80 passed, 2 skipped in 7.30s
```

The 2 skips are pre-existing (live-network tests), not introduced by this feature.

## Quality gates

```
.venv\Scripts\python -m ruff check .
→ All checks passed!            (exit 0)

.venv\Scripts\python -m mypy app
→ Success: no issues found in 34 source files   (exit 0)
```

## Expected after the feature

- Pre-existing scenarios: **80 passed, 2 skipped**, all still green.
- New scenarios: +29 (8 US1, 7 US2, 8 US3, 3 US4, 3 US5).
- `ruff` and `mypy --strict`: still exit 0.

## Actual after the feature (T040)

```
.venv\Scripts\python -m pytest -q
→ 108 passed, 3 skipped in 7.15s
```

- Pre-existing: 80 passed, 2 skipped — **all still green**, none lost (SC-003 satisfied).
- New: +28 passed, +1 skipped = 29 scenarios, exactly as planned (8 US1, 7 US2, 8 US3, 3 US4, 3 US5).
  The 1 new skip is US1's stale-end-of-range scenario, which skips when today is a weekend (2026-10-03
  is a Saturday), following the existing `price_gap_fill` weekend-skip convention.

```
.venv\Scripts\python -m ruff check .      → All checks passed!                      (exit 0)
.venv\Scripts\python -m mypy app          → Success: no issues found in 37 source files  (exit 0)
```

No `type: ignore` was needed for the `@runtime_checkable` Protocol narrowing that T039 flagged as a risk.

## SC-006 measurement (T028a) — PASS

Live service on port 8077, real yfinance data source. Instrument: **ARM** (listed 2023-09-14), requested
over a ~6.75-year window (2019-01-01 → 2025-10-01) with `fill=none`, so the pre-history segment is
empty. Cache and sidecar deleted beforehand.

| Attempt | Elapsed | Entries | Notes |
|---|---|---|---|
| 1st (cold) | 0.486s | 513 | populates cache, records boundary |
| 2nd (warm) | 0.194s | 513 | earlier-segment fetch skipped |

**Ratio: 39.9%** against the 50% threshold — PASS. Identical entry count and window across both
attempts, confirming FR-021 (suppression does not change what the consumer receives).

Sidecar written as expected:

```json
{"no_data_before": "2023-09-14"}
```

`cache_no_earlier_data_recorded` and `cache_no_earlier_data_skip` both present in
`logs/market-data-api.log` with the ticker and boundary.

## Live quickstart verification (T041)

| Check | Result |
|---|---|
| `fill=none` on AAPL 2025-01-02→10 | 5 real observations |
| `fill=all` same range | 7 entries (2025-01-09 NYSE closed, 2025-01-10 filled) |
| Window under `fill=all` | still `2025-01-08` — never derived from a filled value (FR-014) |
| `fill=forward` | 422 with `loc: ["query","fill"]` |
| `DELETE /cache/ARM` | removed `ARM.csv` **and** `ARM.meta.json` (FR-023) |
| `/securities/AAPL/price` with vs without `fill` | byte-identical (FR-010) |
| `GET /docs` | 200, `fill` renders as a dropdown defaulting to `all` |
