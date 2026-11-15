# Quickstart: On-Demand Ladder Rebuild for Stale Requests

## Prerequisites

- An account with an already-ingested position ladder and/or capital ledger whose
  `AccountMeta.to_date` / `CapitalMeta.to_date` is well behind today (e.g. ingested weeks ago).
- The market-data-web-service dependency reachable and returning prices for the gap period.

## 1. Observe today's defect (before this feature)

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload
curl "http://localhost:8000/v1/accounts/HL-ISA/timeseries?attribute=market_value&start=2026-07-01&end=2026-11-06&periodicity=day"
```

Every entry from the account's last ingested date through `2026-11-06` repeats the same
`market_value` — the flat-fill defect.

## 2. Trigger a rebuild (after this feature)

Re-run the same request. The response now:

- Returns a `market_value` for each business day that varies with actual market pricing from
  the last ingested date through the prior business day relative to today.
- Blocks until the rebuild completes (synchronous — Clarifications session 2026-11-10).
- Persists the rebuilt rows: `GET /v1/accounts/HL-ISA/ladder` now shows an updated `to_date`.

## 3. Confirm the rebuild only happens once

```bash
curl "http://localhost:8000/v1/accounts/HL-ISA/timeseries?attribute=market_value&start=2026-07-01&end=2026-11-06&periodicity=day"
```

Repeating the identical request returns immediately from persisted data; no new market-data
calls are made (verify via structured logs — no `market_data_request_succeeded` entries for this
account on the second call).

## 4. Confirm the future-date cap

```bash
curl "http://localhost:8000/v1/accounts/HL-ISA/timeseries?attribute=market_value&start=2026-07-01&end=2026-11-12&periodicity=day"
```

(Assuming today is 2026-11-10 and 2026-11-09 is the prior business day.) The rebuild still only
extends through 2026-11-09; no entry for 2026-11-10 through 2026-11-12 is fabricated —
`FutureEndDateError` still governs any explicit `end` later than today, per existing behaviour.

## 5. Confirm ledger re-ingestion supersedes a projected span

```bash
curl -X POST "http://localhost:8000/v1/accounts/HL-ISA/ladder" \
  -F "file=@ledger-with-october-trade.xlsx"
```

Upload a ledger whose rows include a trade dated inside the previously-rebuilt span (e.g.
2026-10-15). Re-request the timeseries for that date:

```bash
curl "http://localhost:8000/v1/accounts/HL-ISA/timeseries?attribute=market_value&start=2026-10-01&end=2026-10-31"
```

The `market_value` for 2026-10-15 onward now reflects the newly ingested trade, not the earlier
held-constant projection.

## 6. Run the test suite

```bash
python -m pytest
```

New BDD scenarios under `tests/features/` for this feature's three user stories, plus unit tests
for the rebuild orchestration, the lock registry, and the partial/total market-data-unavailable
paths, must all pass alongside the existing suite.
