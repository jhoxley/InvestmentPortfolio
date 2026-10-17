# Phase 0 Research: Risk Page (Return Histogram)

No `NEEDS CLARIFICATION` markers remained in the Technical Context (all defaults follow directly
from existing pages' established patterns), so this phase documents the concrete decisions made
while resolving open design questions, in the same decision/rationale/alternatives format used by
prior features' `research.md` files.

## #1 — How to add a "10Y" shortcut without disturbing existing pages

**Decision**: Add `SHORTCUT_10Y = "10y"` and a `SHORTCUT_10Y: 10` entry in
`date_range_controls.py`'s `_SHORTCUT_YEAR_OFFSETS`, keeping the module's existing five-button
layout (`_build_shortcut_buttons`, `build_account_date_controls(first_shortcut_label=...)`)
unchanged. `risk.py` requests `first_shortcut_label="10Y"` and defines its own
`_SHORTCUT_CODE_BY_BUTTON_ID` mapping the shared first-button DOM id
(`overview-shortcut-ytd`) to `SHORTCUT_10Y`, while its 1Y/3Y/5Y/ALL buttons map to the existing
`SHORTCUT_1Y`/`SHORTCUT_3Y`/`SHORTCUT_5Y`/`SHORTCUT_ALL` codes unchanged.

**Rationale**: This is the exact pattern `performance.py` already established for relabeling the
first button to "ITD" and remapping its code to `SHORTCUT_ALL` (specs/020, research.md #3) — a
page-local code mapping, not a per-page fork of the shared component. Adding the offset itself to
the shared `_SHORTCUT_YEAR_OFFSETS` dict (rather than duplicating `_years_before` logic inside
`risk.py`) keeps the date-math single-sourced, consistent with Principle V (no bespoke
reimplementation of solved logic already in the shared module).

**Alternatives considered**:
- *Fork `date_range_controls.py` for the Risk page's own five-button set*: rejected — duplicates
  clamp/date-math logic the spec explicitly asks to share ("sharing as much default behavior and
  implementation logic as possible").
- *Make the shared component take an arbitrary list of `(code, label)` pairs instead of a
  fixed five-slot layout*: rejected as over-engineering for a single new button; every existing
  page still uses exactly five slots, and the one-button-relabeled approach already generalizes
  cleanly (this is the second page to use it, after Performance).

## #2 — Response model and client shape for `/risk/return-histogram`

**Decision**: Add `StdDevBand`, `HistogramStatistics`, and `ReturnHistogramResponse` Pydantic
models to `src/models/portfolio_analysis.py`, field-for-field matching
`portfolio-analysis-service/app/models/risk.py` (read from source), and a
`get_return_histogram(account_name, start, end) -> ReturnHistogramResponse` method on
`PortfolioAnalysisClient`/`HttpPortfolioAnalysisClient`, following the existing `_get(...)` +
`.model_validate(...)` pattern used by every other client method (e.g. `get_performance`).

**Rationale**: Matches Principle I (UI performs no calculation — it only deserializes and
displays) and Principle V/II (same client layering as every other endpoint call; no bespoke HTTP
handling). `histogram` is typed `list[tuple[int, int]]`, matching the service's own field type, so
Pydantic validates the pair shape for free.

**Alternatives considered**:
- *Reuse `TimeSeriesResponse`/`PositionTimeSeriesResponse`*: rejected — this endpoint's shape
  (`histogram` pairs + a nested `statistics` object) is structurally different from every existing
  timeseries response; forcing it into `extra="allow"` entries would lose the `statistics` object's
  own typed shape.

## #3 — Statistics table: excluding `std_dev_bands`, showing "not available"

**Decision**: `_risk_table.py` builds rows from `HistogramStatistics` in field-declaration order
(count, mean, median, mode, minimum, maximum, std_dev, skewness, kurtosis), explicitly skipping
`std_dev_bands`, and renders any `None` value as a fixed placeholder string ("N/A").

**Rationale**: Directly satisfies spec FR-010 (exclude `std_dev_bands`) and FR-012 (undefined
statistics still appear as a row, not omitted). Iterating the model's own field order (rather than
a hand-maintained row list) means a future field added to `HistogramStatistics` server-side
appears automatically without a second edit — except `std_dev_bands`, which is explicitly excluded
by name since it is a list, not a scalar, and was explicitly called out as out of scope by the
feature request.

**Alternatives considered**:
- *Hand-write the 9 row labels as a static list*: rejected — duplicates information already
  present in the Pydantic model's field order/names, and drifts silently if the service adds a
  field.

## #4 — Table widget choice

**Decision**: `dash_table.DataTable`, matching the existing pattern in
`_positions_chart.py`/`_overview_position_widgets.py`.

**Rationale**: Principle V — reuse the established table component rather than introducing
`dbc.Table` (unused elsewhere in this codebase) or a third option.

**Alternatives considered**:
- *`dbc.Table.from_dataframe`*: rejected — no other page uses pandas DataFrames as a UI-layer data
  shape; this codebase already imports and formats data straight from the pydantic response
  models.

## #5 — 60/40 layout

**Decision**: A single `dbc.Row` with two `dbc.Col`s at `width=7` (chart) and `width=5` (table) —
the nearest 12-column Bootstrap split to 60/40 (58.3%/41.7%).

**Rationale**: Every other page's layout uses Bootstrap's 12-column grid via `dbc.Row`/`dbc.Col`
with integer `width`s (e.g. `shell.py`'s `_CONTENT_WIDTH = 10`); introducing a raw CSS percentage
split would be the only place in the codebase doing so.

**Alternatives considered**:
- *CSS `flex-basis: 60%`/`40%` inline styles*: rejected — inconsistent with the rest of the
  codebase's exclusive use of Bootstrap's column system; no other page mixes the two approaches.
