# Consumed API Contract: `portfolio-analysis-service`

This feature is a **consumer**, not an owner, of these endpoints. The
authoritative contract is
`portfolio-analysis-service/specs/004-account-timeseries-api/contracts/openapi.yaml`
(version 0.4.0, verified against source on 2026-07-16) — this file
summarizes only the parts `src/services/portfolio_analysis_client.py`
depends on, so a future drift in the upstream contract is easy to spot by
diffing against the real file rather than trusting a stale copy here.

## `GET /v1/accounts`

Returns every account with ≥1 ingested resource. Used to populate the
Account selector (FR-001) and to derive each account's default `from` date
(FR-003). No query parameters.

Response shape consumed: `accounts[].{account_name, capital_ledger,
position_ladder}`, where `capital_ledger`/`position_ladder` are each either
`{from_date, to_date}` or `null`.

## `GET /v1/timeseries/attributes`

Returns the full set of chartable metrics. Used to populate the metric
toggle panel (FR-005) with each toggle's tooltip text (FR-006). No query
parameters.

Response shape consumed: `attributes[].{name, description}` (`source` is
parsed but not rendered — see data-model.md).

Known attribute names as of the 0.4.0 contract: `capital`, `income`,
`book_cost`, `market_value`, `pnl`. The client MUST NOT hard-code this list
for populating the toggle panel — it always renders whatever this endpoint
returns, so a new attribute added upstream appears automatically. The fixed
color-per-metric mapping (data-model.md, Chart Series) does hard-code these
five names as its palette keys; an attribute added upstream with no
corresponding color entry falls back to a defined default color rather than
erroring (implementation detail for `tasks.md`, not a spec requirement).

## `GET /v1/accounts/{account_name}/timeseries`

Returns the actual chart data. Called only once an account, valid from/to
range, and ≥1 toggled-on metric are all selected (FR-008).

| Param | In | Sent as |
|---|---|---|
| `account_name` | path | Selected `Account.account_name`, URL-encoded |
| `attribute` | query, repeated | One entry per toggled-on `Performance Metric.name` |
| `start` | query | Selected/derived `from_date` (ISO `date`) |
| `end` | query | Selected/derived `to_date` (ISO `date`) |

Response shape consumed: `entries[].{date, ...requested attribute values}`.
`account_name`, `attributes`, `from_date`, `to_date`, and `_links` are
parsed onto the typed response model for completeness but this feature has
no requirement that reads them back out (they're echoes of the request,
already known client-side).

## Error handling contract

| Upstream status | Client behavior |
|---|---|
| `404` (no ledger/ladder ingested for account) | Should not occur in practice — `/v1/accounts` only lists accounts with ≥1 ingested resource, so a selected `account_name` always has data; if it somehow occurs, treat as `overview-error-state` (FR-014), not a silent empty chart |
| `422` (validation failure — bad range, unknown attribute, etc.) | `overview-error-state` (FR-014) — this shouldn't be reachable in normal use since the UI itself enforces valid dates (FR-015) and only sends attribute names it just received from `/v1/timeseries/attributes`, but a defensive display avoids a broken/blank chart if the two services' attribute sets ever drift |
| Any non-2xx, timeout, or connection error | `overview-error-state` (FR-014), logged via `structlog` per research.md #5 |
| `200` with `entries: []` | `overview-empty-state` (FR-013) — a valid response with no data points for the selected range, not an error |
