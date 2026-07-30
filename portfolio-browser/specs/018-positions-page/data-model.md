# Phase 1 Data Model: Positions Page

This feature reuses `Account` and `Reporting Period Shortcut`/`Date Range`
unchanged from `016-link-real-portfolio`/`017-chart-date-range-shortcuts`
(`specs/016-link-real-portfolio/data-model.md`,
`specs/017-chart-date-range-shortcuts/data-model.md`) — not reproduced
here except where this feature adds a new derivation. Everything below is
new to this feature.

## Position (new)

One entry from `GET /v1/accounts/{account_name}/positions`. Modeled as
`src/models/portfolio_analysis.py::PositionSummary`.

| Field | Type | Notes |
|---|---|---|
| `position` | `str` | Display name (e.g. `"Apple Inc"`, `"Cash"`); may contain spaces/symbols. |
| `from_date` | `date` | Earliest date this position has recorded data. |
| `to_date` | `date` | Latest date this position has recorded data. |

`PositionsResponse` wraps `positions: list[PositionSummary]` plus
`account_name`/`_links`, mirroring the existing `AccountsResponse`-style
wrapper pattern already used for `/v1/accounts`.

## Position Attribute (reused, not new)

`GET /v1/positions/attributes` returns the same `{name, description,
source}` shape as `GET /v1/timeseries/attributes` — the existing
`src/models/portfolio_analysis.py::AttributeDefinition` model is reused
verbatim (see research.md #2). No new model.

Known attribute names per the `005-position-timeseries-api` contract:
`market_value`, `income`, `book_cost`, `pnl`, `close_price`, `quantity`.
The client MUST NOT hard-code this list — it always renders whatever
`/v1/positions/attributes` returns.

## Position Time Series Entry / Response (new)

One row from `GET /v1/accounts/{account_name}/position`. Modeled as
`src/models/portfolio_analysis.py::PositionTimeSeriesEntry`/
`PositionTimeSeriesResponse`, structurally parallel to the existing
`TimeSeriesEntry`/`TimeSeriesResponse` (016) but with an added `position`
field per entry:

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | One business day within `[from_date, to_date]`. |
| `position` | `str` | Which position this row belongs to. |
| *(dynamic)* | `float` | One key per requested attribute (`extra="allow"`, same pattern as `TimeSeriesEntry`). |

`PositionTimeSeriesResponse`: `account_name`, `attributes: list[str]`,
`positions: list[str]`, `from_date`, `to_date`,
`entries: list[PositionTimeSeriesEntry]`, `links: dict[str, str]`.

## Chart Visualization Mode (new, local-only)

Not fetched, not persisted server-side — a single `dbc.Switch` value
(`positions-parameters-stacked-toggle`) held in the browser session only
(never sent to the backing service; spec Assumptions).

| Value | Meaning | Constraint |
|---|---|---|
| `False` (default) | Line chart — one `go.Scatter` trace per (position, attribute) pair, `mode="lines+markers"`, no `stackgroup`. | Always available. |
| `True` | Stacked area chart — one `go.Scatter` trace per position, shared `stackgroup` (research.md #4). | Only settable while exactly one attribute is selected (FR-009/FR-011); auto-reset to `False` the instant a second attribute is selected (FR-010). |

## Position Color Assignment (new, derived — not stored)

A pure function, not a fetched or persisted entity:
`_color_for_position(position_name: str) -> str` (research.md #5).
Deterministic: `hashlib.sha256(position_name.encode()).digest()` → integer
→ modulo 50 → index into a fixed, pre-generated 50-color HSL-wheel
palette. Same input always yields the same output within a process and
across process restarts (no `PYTHONHASHSEED`-salted `hash()` involved).

## Position Comparison Row (new, derived — not fetched, computed client-side)

One row of the comparison table (FR-017–FR-019), derived entirely from an
already-fetched `PositionTimeSeriesResponse` — a purely presentational
transform (constitution Principle I's carve-out), not a new financial
calculation: no value is computed that the API didn't already return
verbatim.

| Field | Type | Derivation |
|---|---|---|
| `position` | `str` | From `entries[].position`, one row per distinct value present in the response. |
| *(per selected attribute)* `{attribute}` | `float \| None` | The entry for this `position` where `date == to_date`; `None` if absent (excluded row per FR-025, not a blank cell — see Edge Cases). |
| *(per selected attribute)* `{attribute} (prev)` | `float \| None` | The entry for this `position` where `date == from_date`. |
| *(per selected attribute)* `{attribute}` cell shading | `"up" \| "down" \| "flat"` | `"up"` if `{attribute} > {attribute} (prev)`, `"down"` if `<`, `"flat"` if `==` — feeds `DataTable.style_data_conditional` (research.md #6), mapped to light-green/light-red/unshaded respectively (FR-019). |

Rows are included only for positions with at least one entry in the
response (FR-017); a position present in the position filter but absent
from `entries` (FR-025's exclusion case) produces no row at all.

**Value formatting (FR-008a)**: both `{attribute}`/`{attribute} (prev)`
values in the table and the chart's own axis/hover text are formatted via
one shared `_format_attribute_value(attribute_name, value) -> str`
helper in `_positions_chart.py`: currency style (`£`, thousands separator,
2dp) for `market_value`/`income`/`book_cost`/`pnl`/`close_price`, plain
numeric (no symbol) for `quantity` — a lookup table keyed by attribute
name, mirroring `ATTRIBUTE_COLORS`' fixed-mapping-with-default shape in
`_overview_chart.py`.

## State flow summary

```text
Page mount (positions.py)
  → fetch /v1/accounts (shared with Overview) + /v1/positions/attributes
  → default: first account (alphabetical), attribute toggles default
      per spec Assumptions (market_value on), Stacked-area off
  → fetch /v1/accounts/{account}/positions
      → populate position multi-select, default: all positions selected
  → apply "YtD" via the shared `_shortcut_from_date(SHORTCUT_YTD, account,
      today)` (research.md #1) → from = 1 Jan current year, clamped to the
      account's earliest recorded date; to = last business day (FR-012).
      Deliberately NOT a call to Overview's own account-default sync
      (which yields the account's full history) — Positions' own default
      range is always "YtD", both on first load and on every subsequent
      account switch (spec `/speckit-analyze` remediation, 2026-07-17)

Any of {account, from, to, shortcut click, attribute toggle,
position filter, stacked-area toggle} changes
  → (if stacked-area is on and a 2nd attribute was just toggled on:
      auto-set stacked-area False first — FR-010)
  → GET /v1/accounts/{account}/position?position=...&attribute=...&start=...&end=...
  → build chart (line or stacked-area per current toggle value)
  → build comparison table (Position Comparison Row derivation above)
  → both render together from the same response (FR-013, SC-006) —
      never two separate fetches that could disagree
```
