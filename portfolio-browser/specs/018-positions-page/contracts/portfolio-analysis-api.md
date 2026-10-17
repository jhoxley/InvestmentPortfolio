# Consumed API Contract: `portfolio-analysis-service`

This feature is a **consumer**, not an owner, of these endpoints. The
authoritative contract is
`portfolio-analysis-service/specs/005-position-timeseries-api/contracts/openapi.yaml`
(version 0.5.0, verified against source on 2026-07-17) — this file
summarizes only the parts `src/services/portfolio_analysis_client.py`
depends on. `GET /v1/accounts` is already consumed by
`016-link-real-portfolio`/`017-chart-date-range-shortcuts` (see
`specs/016-link-real-portfolio/contracts/portfolio-analysis-api.md`) and is
reused verbatim by this feature — not repeated here.

## `GET /v1/accounts/{account_name}/positions`

Enumerates every position recorded for an account. Used to populate the
position multi-select (FR-005) and its "select all by default" initial
state (FR-012). No query parameters beyond the path's `account_name`.

Response shape consumed: `positions[].{position, from_date, to_date}`.
`account_name`/`_links` are parsed onto the typed response model for
completeness but not read back out by this feature.

| Upstream status | Client behavior |
|---|---|
| `404` (no resource ingested for account) | `positions-error-state` (mirrors `overview-error-state`; FR-022) |
| `422` (account known, no position ladder ingested) | `positions-empty-state` (FR-020's "no data" pattern — this account has no positions to show, not a broken request) |

## `GET /v1/positions/attributes`

Returns the set of chartable/tabulable position attributes. Used to
populate the attribute toggle panel (FR-004), reusing the exact same
`AttributeDefinition` model and toggle-rendering component
`GET /v1/timeseries/attributes` already uses (research.md #2) — this
endpoint differs only in URL and in which attribute names it returns
(`market_value`, `income`, `book_cost`, `pnl`, `close_price`, `quantity`;
notably no `capital`, unlike the account-level endpoint). No query
parameters.

Response shape consumed: `attributes[].{name, description}` (`source`
parsed but not rendered, matching the existing Overview precedent).

## `GET /v1/accounts/{account_name}/position`

Returns the actual per-position chart/table data. Called only once an
account, valid from/to range, ≥1 selected position, and ≥1 toggled-on
attribute are all present (FR-013, FR-020, FR-021).

| Param | In | Sent as |
|---|---|---|
| `account_name` | path | Selected `Account.account_name` |
| `position` | query, repeated | One entry per currently-selected position filter entry, sent explicitly even when every position happens to be selected — the endpoint treats an explicit full list and an omitted parameter identically (per its own contract's "if omitted entirely, every position... is included"), so no client-side "is everything selected" comparison is needed; simpler and avoids an unspecified piece of comparison logic (`/speckit-analyze` remediation, 2026-07-17) |
| `attribute` | query, repeated, required | One entry per toggled-on `Position Attribute.name` |
| `start` | query | Selected/derived `from_date` (ISO `date`) |
| `end` | query | Selected/derived `to_date` (ISO `date`) |

Response shape consumed: `entries[].{date, position, ...requested
attribute values}` — feeds both the chart (grouped by `position`, per
research.md #4/#5) and the comparison table (data-model.md's Position
Comparison Row, filtered to `date in {from_date, to_date}`).

## Error handling contract

| Upstream status | Client behavior |
|---|---|
| `404` (no resource ingested for account) | `positions-error-state` (FR-022) |
| `422` (validation failure — bad range, unsupported attribute, unresolvable start date, etc.) | `positions-error-state` (FR-022) — should not be reachable in normal use since the UI only sends attribute/position names it just received from this account's own `/v1/positions/attributes` and `/v1/accounts/{account}/positions` responses, and enforces valid date ranges the same way Overview already does, but a defensive display avoids a broken/blank page if the services' data ever drifts |
| Any non-2xx, timeout, or connection error | `positions-error-state` (FR-022), logged via `structlog`, same pattern as Overview's client error handling |
| `200` with `entries: []` | `positions-empty-state` (FR-020/FR-021's "no data" pattern) — a valid response with no data points for the current selection, not an error |
