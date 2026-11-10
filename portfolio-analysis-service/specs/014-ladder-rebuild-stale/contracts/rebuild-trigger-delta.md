# Contract Delta: On-Demand Ladder Rebuild Across Existing GET Endpoints

Baseline: the existing OpenAPI definitions for the endpoints below (see `app/api/*.py` for their
current `@router.get(...)` docstrings/response models). Only the items below change; paths, query
parameters, and status codes are otherwise unchanged.

## Affected endpoints

- `GET /v1/accounts/{account_name}/timeseries`
- `GET /v1/accounts/{account_name}/position`
- `GET /v1/accounts/{account_name}/performance`
- `GET /v1/accounts/{account_name}/risk/return-histogram`

Not affected (no requested date range to compare against a last-ingested-or-rebuilt date):
`GET /v1/accounts/{account_name}/ladder`, `GET /v1/accounts/{account_name}/ladder/download`,
`GET /v1/accounts/{account_name}/capital`, `GET /v1/accounts/{account_name}/capital/download`,
`GET /v1/accounts`, and `GET /v1/accounts/{account_name}/positions` — verified against
`app/api/position_timeseries.py`'s `list_account_positions`: it takes no `start`/`end` query
parameters and reads `ladder_repo.read_full_df()` directly, never going through
`PositionTimeSeriesService`. It already satisfies FR-011 by construction — once another endpoint
persists a rebuild, this endpoint's next read reflects the updated file with no code change.

## Changed semantics (documentation only; existing response schemas are extended, not replaced)

1. Before composing its response, each affected endpoint now compares its resolved end date
   against the relevant resource's last-ingested-or-rebuilt date (`AccountMeta.to_date` /
   `CapitalMeta.to_date`). If the resolved end date is later, the endpoint synchronously rebuilds
   the missing period (carrying the last known positions forward, repriced with fresh market
   data) before returning (FR-001–FR-004, FR-012).
2. The rebuild target is capped at the prior business day relative to the day of the request —
   never the current day, never a future date (FR-003).
3. If the market data needed for the rebuild is **entirely** unavailable, the endpoint falls back
   silently to the previous (pre-rebuild) flat-filled response for that request only; nothing is
   persisted, and the next request will retry the rebuild (FR-013). No new error response is
   introduced for this case — the existing success response shape is reused.
4. If the market data needed for the rebuild is **partially** unavailable, the response's
   affected numeric field(s) for the unresolved date(s) are serialised as JSON `null` instead of
   a number. Every attribute field that was previously typed as a non-nullable number in the
   response schema becomes nullable (`number` → `["number", "null"]` in OpenAPI terms) to
   accommodate this (FR-010).
5. No new query parameters, path parameters, or status codes are introduced. No existing
   successful-response status code changes. `_links` are unchanged.

## Schema changes

### `TimeSeriesEntry` (`GET .../timeseries`)

Each dynamically-added attribute field (`capital`, `income`, `book_cost`, `market_value`, `pnl`)
becomes nullable. Example, requesting `market_value` for a date affected by a partial rebuild
gap:

```json
{ "date": "2026-10-14", "market_value": null }
```

### Position/performance/return-histogram entry schemas

The same nullability extension applies to each endpoint's own per-date numeric field(s)
(e.g. position-level `market_value`, performance return/PnL fields). No field is renamed or
removed.

## Unchanged

- RFC 7807 error shapes for every existing error case (404 account not found, 422 validation,
  502 `market_data_service_error` for a *synchronous ingestion* call — unaffected by this
  feature's fallback behaviour in item 3 above, which deliberately avoids raising that error for
  a rebuild-triggering read).
- HATEOAS `_links` structure.
- Request parameters and their validation rules.

## Action

For each affected router module (`app/api/timeseries.py`, `app/api/position_timeseries.py`,
`app/api/performance.py`, `app/api/risk.py`), append a sentence to the endpoint's docstring/
OpenAPI `description` noting that a stale request triggers a synchronous rebuild capped at the
prior business day, and that affected fields may be `null` when pricing was unavailable.
