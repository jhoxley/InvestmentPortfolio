# Phase 0 Research: Projection Page (replaces Income)

## 1. New analysis-service capability: contract design (FR-018)

**Decision**: A new endpoint, `GET /v1/accounts/{account_name}/projection`, reusing
`PositionTimeSeriesResponse`'s exact response shape, with the `position` discriminator
field repurposed as a **series label** (`"Historical"`, `"1Y"`, `"3Y"`, `"5Y"`, `"Ann. ITD"`)
instead of a position name.

Request parameters (query string):

| Param | Type | Required | Meaning |
|---|---|---|---|
| `start` | date | No | Defaults to the account's position ladder `to_date` (its most recently recorded date) — per the spec's own instruction that "leaving this input blank on the API should also default to the most recent date that has data for the given account." |
| `projection_date` | date | Yes | Must be strictly later than the resolved `start`. The API has no concept of "1Y/5Y/10Y/20Y" — those are resolved to an explicit date client-side before this parameter is set (FR-004's "the explicit date option is a simple pass-through to the API," spec verbatim). |
| `periodicity` | str | No | Same enum as feature 008 (`day`/`week`/`month`/`quarter`/`annual`), default `day`. |
| `return` | str, repeatable | No | Zero or more of `itd_ann`, `1y`, `3y`, `5y` (the wire-format names `performance_attributes.py` already validates, minus plain `itd`). Zero supplied → historical series only (FR-013). |

Response: identical shape to `PositionTimeSeriesResponse`, with `attributes: ["market_value"]`
fixed, and `positions` renamed in spirit (kept as the same field name for wire-compatibility
with the browser's existing model, so it needs no new Pydantic class — see Data Model) but
populated with series labels: `["Historical", "1Y", "5Y"]` etc., always including `"Historical"`.

**Rationale**: The spec's own words are explicit: "The payload response from the API is the
same structure as the 'positions' and 'overview' page." Reusing `PositionTimeSeriesResponse`
rather than inventing a new response model means the browser's existing
`PositionTimeSeriesResponse` parsing/plotting code (already proven on the Positions page,
which draws one line/area per distinct `position` value) needs *zero* new parsing logic —
only a new client method and a page that asks for it. This is also why the fake-client test
pattern already used in `tests/bdd/steps/*_steps.py` extends cleanly: the fake only needs to
compute different `position` labels and values, not a new payload shape.

**Alternatives considered**:
- A bespoke `ProjectionResponse` model with an explicit `series: [{label, entries: [...]}]`
  nesting. Rejected — the spec asks for structural reuse, and the flat
  `PositionTimeSeriesResponse` shape already renders correctly through the existing "group by
  position, one trace per group" charting pattern (`_performance_chart.py`'s sibling for
  positions), so a nested shape would need new charting code for no behavioural gain.

**Explicitly out of scope for this plan/feature's own tasks**: implementing this endpoint
server-side. Per the spec's Assumptions, the capability "does not exist yet and is a
prerequisite dependency for this feature, to be specified and built as its own effort" in
`portfolio-analysis-service`. This document pins its contract (below, and in
`contracts/portfolio-analysis-api.md`) so that effort — and this feature's own browser-side
work, built against a fake client implementing the same contract — can proceed independently
without the interface drifting between them.

## 2. Projection math (FR-018's "own historical rate")

**Decision**: For a requested return `r` (an annualized rate, e.g. the account's `ITD (Ann.)`,
`1Y`, `3Y`, or `5Y` performance measure as of the resolved start date), the daily projection
rate is:

```text
daily_rate = r * sqrt(260)
```

and each subsequent business day's projected market value compounds from the start date's
actual market value `V0`:

```text
V(t) = V0 * (1 + daily_rate) ** t       # t = business days elapsed since start
```

This produces one row per business day from `start` (exclusive) to `projection_date`
(inclusive); `periodicity` bucketing (feature 008's `aggregate_last_observation`) is then
applied as an overlay on top of this daily series, exactly as it already is for historical
data — never baked into the compounding itself.

**Rationale**: This is the exact, explicit formula given in the original feature request
("Take the annualized 3Y or 5Y return, multiply by sqrt(260) to get the daily return, then
project forward the last market_value daily by this return, applying periodicity buckets as
an overlay afterwards"), and the spec's own Key Entities section deliberately left the precise
formula unstated at the spec level ("each point reflecting the compounding effect of that
return's own historical rate applied since the start date") while flagging in the
`requirements.md` checklist that the exact math is a plan-level decision still to be pinned.
It is recorded here verbatim rather than "corrected" to a more conventional
de-annualization (`(1+r)**(1/260)-1`) because the request was unambiguous and specific, and
the spec's Assumptions are explicit that this is "a straightforward, transparent forward
compounding" with no claim to statistical rigor — an illustrative projection, not a modeled
forecast.

**Alternatives considered**:
- Geometric de-annualization `(1 + r) ** (1/260) - 1` — the conventional way to turn an
  annualized return into a daily compounding rate. Rejected in favor of the literal,
  explicitly-specified formula above; noted here so a future reviewer does not "fix" this
  into the conventional form without knowing it was a deliberate, spec-sourced choice.

## 3. Periodicity bucketing reuse for the projected leg

**Decision**: The future capability computes the full daily projected series per requested
return exactly as described above, then reuses feature 008's existing
`app/services/periodicity_aggregation.py::aggregate_last_observation()` unmodified, called
once per series label (`"Historical"` and once per requested return) — identical to how
`position_timeseries_service.py` already aggregates each position independently today, just
with "series label" standing in for "position name." No new aggregation logic is required in
the analysis service; this is a call-site reuse, not a new capability.

**Rationale**: `aggregate_last_observation()`'s window-dating (`_window_start_date`) is a
pure function of the calendar period and the caller's own `resolved_start` — never of the
frame's contents — so historical and projected windows computed independently still land on
identical window boundaries when concatenated for the same date range, satisfying FR-016
("a consistent, calendar-aligned interval across the whole combined span") for free.

## 4. UI: horizon buttons, calendar picker, start-date control

**Decision**:
- **Horizon buttons** ("1Y"/"5Y"/"10Y"/"20Y"): a `dbc.ButtonGroup`, following the existing
  Reporting Period Shortcut precedent (`date_range_controls.py`) — `n_clicks`-driven for the
  same unambiguous-intent reason established in 021's research.md #1. Each click computes
  `start_date + N years` using the existing `_years_before`-equivalent date arithmetic
  (a new `_years_after` mirroring it, since horizons look forward not back) — a purely
  presentational date computation, explicitly permitted under Principle I (same carve-out
  021 already relies on for its interval-derivation rule).
- **Calendar picker**: a single `dcc.DatePickerSingle`, mirroring `app-parameters-from-date`/
  `to-date`'s existing pattern, with `min_date_allowed` bound to the day after the current
  start date (client-side guard) and a paired `dbc.FormText`/`dbc.Alert` for the FR-014
  inline validation message when the service itself rejects a date (belt-and-braces: the
  client-side `min_date_allowed` prevents most invalid picks, but a stale `start_date` — e.g.
  changed in another control before the picker re-renders — still needs the server-validated
  path, so the inline message is driven by the actual response/validation, not only by the
  picker's own constraint).
- **Single source of truth for "projection date in effect"** (FR-006): a page-local
  `dcc.Store` (`projection-target-store`), written by *either* the horizon buttons or the
  calendar picker's `n_clicks`/date-change — identical single-writer pattern to 021's
  periodicity store, so "whichever was used most recently wins" falls out of normal Dash
  Input-to-Output flow with no extra bookkeeping, and the calendar control is unconditionally
  synced from the store's value (`Output("projection-target-date", "date")`) so it always
  displays what's in effect, satisfying FR-006's second half directly.
- **Start date control**: a `dcc.DatePickerSingle` (`projection-start-date`), defaulting to
  the selected account's most recent recorded date on account selection/switch (mirroring
  Performance's own `_sync_date_range_to_selected_account`, but syncing to the account's
  `to_date` rather than resetting a from/to range) — confirmed as a **visible, editable
  control** per this feature's own `/speckit-clarify` session.

**Rationale**: Every new control follows an existing, already-reviewed pattern in this
codebase (ButtonGroup for discrete choices, DatePickerSingle for dates, dcc.Store for
single-writer state) rather than introducing new UI machinery, satisfying Principle V.

## 5. Returns selection control

**Decision**: Reuse `src/components/attribute_toggles.py`'s `build_attribute_toggles()`
unmodified, called with the four fixed labels `["Ann. ITD", "1Y", "3Y", "5Y"]` (in that
order, matching the spec's own enumeration and User Story 3's scenario labels) rather than
an API-driven attribute list. `/v1/performance/attributes` cannot be filtered server-side to
exclude plain `ITD` without changing that shared endpoint (which Performance itself still
needs unfiltered, per the spec's Assumption that "this feature does not change... the
Performance page"), so this page's toggle set is built from a small, page-local, fixed
`AttributeDefinition` list rather than plumbing an exclusion parameter through a shared
endpoint for one caller. Colors reuse `_performance_chart.py`'s existing
`PERFORMANCE_ATTRIBUTE_COLORS` mapping for the three shared keys (`1Y`/`3Y`/`5Y`); `"Ann. ITD"`
gets its own new mapping entry in `_projection_chart.py` since Performance's own palette uses
the different key `"ITD (Ann.)"` for the same concept (spec Assumptions: same calculation,
different display label here — the color mapping key must match the display label used on
*this* page).

**Rationale**: Minimal new surface — one small page-local constant list — instead of
extending a shared, cross-page endpoint contract for a single caller's exclusion need.

## 6. Client + model additions

**Decision**: `PortfolioAnalysisClient` Protocol gains one method,
`get_projection(account_name, start, projection_date, returns, periodicity=None)
-> PositionTimeSeriesResponse` (reusing the existing model — see #1), added alongside the
other methods in `portfolio_analysis_client.py`, following the exact same `_get()` /
`model_validate()` / `_warn_if_periodicity_ignored()` pattern already used by
`get_position_timeseries()`. No new Pydantic model is needed on the browser side either —
`PositionTimeSeriesResponse` already exists in `src/models/portfolio_analysis.py`.

**Rationale**: Zero new response-shape code on either side of the wire; the entire feature's
data-access footprint is one new client method mirroring an existing one almost line for line.
