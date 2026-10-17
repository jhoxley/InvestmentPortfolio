# Phase 0 Research: Date Range Shortcut Buttons on Overview

## 1. Disabling the buttons during a refresh (FR-013)

- **Decision**: Use Dash's native `running=[(Output(...), True, False), ...]`
  parameter on the existing `_render_chart` callback (`src/pages/overview.py`),
  targeting each of the five new buttons' `disabled` prop.
- **Rationale**: `running=` is a first-class Dash callback feature (verified
  present and working on a *regular synchronous* callback, not just
  background callbacks, via a spike test against the installed Dash 4.4.0 —
  `dash.callback(..., running=[...])`'s signature does not require
  `background=True`). It declaratively sets the target prop the instant the
  callback starts and restores it the instant the callback returns,
  covering every trigger path FR-013 names (shortcut click, manual date
  edit, account switch, initial load) for free, since all four already
  funnel through this one `_render_chart` callback in 016's existing
  design — no new state-tracking code needed.
- **Alternatives considered**: A hand-rolled `dcc.Store(id="overview-loading")`
  flipped by a pair of callbacks (one to set True before fetch, one to set
  False after) — rejected: `running=` already solves this exact problem
  natively (constitution Principle V: prefer the library's own mechanism
  over a bespoke one); `dcc.Loading`'s `target_components` prop — inspected
  the installed package's prop metadata directly and confirmed it means the
  *opposite* of what's needed (it declares which components' updates
  should trigger showing *a* spinner, not which components to disable) —
  rejected as not fitting.

## 2. Computing "1Y"/"3Y"/"5Y" (exact calendar-date offsets)

- **Decision**: `today.replace(year=today.year - n)`, with a `try`/`except
  ValueError` fallback to `day=28` for the one case where this raises
  (`today` is 29 February and `today.year - n` is not a leap year).
- **Rationale**: stdlib `datetime.date.replace()` covers the general case
  in one line; the leap-day edge case is rare (affects at most one calendar
  date per year, only when a shortcut span crosses a leap year boundary)
  and is fully handled in three lines with no new dependency.
- **Alternatives considered**: `python-dateutil`'s `relativedelta` (handles
  this natively) — rejected: pulling in a new dependency for one narrow
  edge case a three-line stdlib fallback already covers cleanly is
  disproportionate, and 016 already established the project's preference
  for avoiding a date-math library for similarly narrow needs (its own
  `_last_business_day` is plain stdlib `timedelta` looping, not a business-day
  calendar library).

## 3. Reusing the existing render pipeline instead of new fetch/render logic

- **Decision**: The new shortcut callback (`_apply_date_range_shortcut`)
  only computes and sets `app-parameters-from-date.date` /
  `app-parameters-to-date.date` — the exact same two props the manual date
  pickers already set. It does **not** call `_render_timeseries` or touch
  `overview-chart-container` itself.
- **Rationale**: `_render_chart` (016) already has
  `Input("app-parameters-from-date", "date")` and
  `Input("app-parameters-to-date", "date")` — Dash's callback graph means
  setting those two props from *any* source (a picker, or now a shortcut
  button) automatically re-triggers `_render_chart`, satisfying FR-010
  ("trigger a fresh chart request... with no further action") with zero
  new fetch/render code. This is the most direct expression of "reuse the
  existing architecture" the constitution's SOLID guidance calls for.
- **Alternatives considered**: Having the shortcut callback call
  `_render_timeseries` directly and write to `overview-chart-container`
  itself — rejected: this would duplicate `_render_chart`'s guard logic
  (account/date presence checks, zero-metric empty-state) and create a
  second code path that could drift from the picker-driven one; also not
  possible as a *third* callback targeting the same Output without
  `allow_duplicate=True` sprawl for no benefit.

## 4. Identifying which button was clicked

- **Decision**: Five separate `Input(button_id, "n_clicks")` on one
  callback, using `dash.ctx.triggered_id` inside the callback body to look
  up which shortcut fired (a small `dict[str, str]` mapping button DOM id →
  shortcut code).
- **Rationale**: `ctx.triggered_id` is the standard, documented Dash 2.4+
  pattern for "one callback, multiple same-shaped buttons, tell them
  apart" — matches Dash's own recommended pattern for this exact shape of
  problem, avoiding five near-duplicate callbacks (which would also each
  need to target the same Output, requiring `allow_duplicate=True` five
  times over for no benefit).
- **Alternatives considered**: Pattern-matching IDs (`{"type": "shortcut",
  "period": ALL}`), as already used for the metric toggles in 016 —
  considered, but rejected here: pattern-matching IDs exist to handle a
  *dynamic, server-data-driven* number of components (the metric toggles'
  count depends on `/v1/timeseries/attributes`'s response). These five
  buttons are a fixed, spec-defined set that will never change at runtime,
  so plain distinct IDs are simpler and match the "five buttons is a fixed
  UI structure, not repeated user-provided data" nature of this control.

## 5. `allow_duplicate=True` requirement

- **Decision**: Add `allow_duplicate=True` to both `_render_chart`'s two
  `app-parameters-from-date`/`to-date` **State**s (no change needed there —
  States don't require it) and to both callbacks' **Outputs** on
  `app-parameters-from-date.date`/`app-parameters-to-date.date`: the
  existing `_sync_date_range_to_selected_account` (016) and the new
  `_apply_date_range_shortcut` (017) now both target those same two
  Outputs, which Dash requires `allow_duplicate=True` for.
- **Rationale**: Dash's single-callback-per-Output rule (already
  encountered and worked around identically in 016 for
  `overview-chart-container`) applies here too — this is a mechanical,
  well-understood consequence of the design in #3 above, not a new pattern.
- **Alternatives considered**: None — this is Dash's only supported
  mechanism for two callbacks to legitimately target the same Output.
