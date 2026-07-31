# Consumed API Contract: `portfolio-analysis-service`

This feature is a **consumer**, not an owner, of these endpoints. The
authoritative contract is
`portfolio-analysis-service/specs/007-performance-endpoints/contracts/openapi.yaml`
(version 0.7.0, verified against source on 2026-07-30) — this file
summarizes only the parts `src/services/portfolio_analysis_client.py`
depends on. `GET /v1/accounts` is already consumed by
`016-link-real-portfolio` (see
`specs/016-link-real-portfolio/contracts/portfolio-analysis-api.md`) and is
reused verbatim by this feature — not repeated here.

## `GET /v1/performance/attributes`

Returns the set of chartable performance measures. Used to populate the
measure toggle panel (FR-006), reusing the exact same `AttributeDefinition`
model and toggle-rendering component `GET /v1/timeseries/attributes`/
`GET /v1/positions/attributes` already use (research.md #1, #5) — this
endpoint differs only in URL and in which measure names it returns (`ITD`,
`ITD (Ann.)`, `1Y`, `3Y`, `5Y`). No query parameters.

Response shape consumed: `attributes[].{name, description}` (`source` parsed
but not rendered, matching the existing Overview/Positions precedent).

## `GET /v1/accounts/{account_name}/performance`

Returns the actual chart data. Called only once an account, a valid
from/to range, and ≥1 toggled-on measure are all present (FR-010, FR-011).

| Param | In | Sent as |
|---|---|---|
| `account_name` | path | Selected `Account.account_name` |
| `attribute` | query, repeated, required | One entry per toggled-on `Performance Measure.name` |
| `start` | query | Selected/derived `from_date` (ISO `date`) |
| `end` | query | Selected/derived `to_date` (ISO `date`) |

Response shape consumed: `entries[].{date, ...requested measure values}` —
feeds the chart directly (`_performance_chart.py::_build_figure`). Per the
upstream contract, "Trailing and inception-to-date measures always look
back as far as their definition requires, regardless of the requested start
date — only dates within the resolved window appear in the response," and
"a measure not yet computable for a given date... is simply omitted from
that date's entry" (FR-014) — the client performs no client-side
recomputation or backfill of a missing measure value.

## Error handling contract

| Upstream status | Client behavior |
|---|---|
| `404` (no resource ingested for account) | `performance-error-state` (mirrors `overview-error-state`; FR-013) |
| `422` (validation failure — account known but no position ladder ingested, no attribute supplied, unsupported attribute name, invalid date range, or future end date) | `performance-error-state` (FR-013) — should not be reachable in normal use since the UI only sends measure names it just received from `/v1/performance/attributes` and enforces valid date ranges the same way Overview already does, but a defensive display avoids a broken/blank page if the services' data ever drifts |
| Any non-2xx, timeout, or connection error | `performance-error-state` (FR-013), logged via `structlog`, same pattern as Overview's/Positions' client error handling |
| `200` with `entries: []` | `performance-empty-state` (FR-012's "no data" pattern) — a valid response with no data points for the current selection, not an error |
