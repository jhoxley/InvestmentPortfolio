# Phase 0 Research: Positions Page

## 1. Sharing Account/From/To/shortcut controls between Overview and Positions

- **Decision**: Extract the Account selector + "From"/"To" date pickers +
  five shortcut buttons — currently built inline by
  `src/layout/shell.py::_build_overview_parameters_bar()`, and the
  `_earliest_from_date`/`_last_business_day`/`_shortcut_from_date`/
  `SHORTCUT_*` pure helpers currently in `src/pages/_overview_chart.py` —
  into one new shared module, `src/components/date_range_controls.py`.
  Both `_build_overview_parameters_bar()` and a new
  `_build_positions_parameters_bar()` call the same
  `build_account_date_controls()` builder for their common portion; both
  `overview.py` and `positions.py` import the same shortcut/date-math
  functions instead of each maintaining a copy.
- **Rationale**: The spec's own Assumptions section (and FR-003/FR-004)
  require these controls to look and behave *identically* on both pages.
  01. clarification confirmed the "All"/shortcut earliest-date clamp uses
  the same whole-account value on both pages (sourced from the same
  `/v1/accounts` endpoint both pages already call) — meaning there is no
  actual per-page behavioral difference to parameterize, only a single
  shared implementation to extract. This directly satisfies the "share the
  same implementation" refactor the spec calls for, and the constitution's
  SOLID guidance (single responsibility, no duplicated logic).
  Component IDs are unchanged (`app-parameters-account`,
  `app-parameters-from-date`, `app-parameters-to-date`,
  `overview-shortcut-*`/reused for both pages) because only one route's
  parameters bar is ever mounted in the DOM at a time (`shell.py`'s
  existing `_render_parameters_bar()` swap-by-pathname) — there is no ID
  collision risk to design around.
- **Alternatives considered**: Parameterizing the shared builder with a
  per-page "earliest date" API endpoint — rejected once the
  `/speckit-clarify` decision fixed both pages to the *same* account-level
  earliest-date source; adding an unused parameter for a difference that
  doesn't exist would violate YAGNI. Keeping two independent copies (one
  per page) — rejected: the spec explicitly calls for shared behavior, and
  two copies drifting apart over time (e.g. a future clamp-logic bug fixed
  in one but not the other) is exactly the risk sharing eliminates.

## 1a. Positions' own default date range diverges from Overview's (scope correction)

- **Decision**: The *shortcut/clamp* logic (this section) and the
  *account-selected-or-switched default range* logic are two distinct
  mechanisms, and only the former is identical between the two pages.
  Positions' own account-change handler calls
  `_shortcut_from_date(SHORTCUT_YTD, account, today)` (the same function
  the "YtD" button itself calls) to compute its default range, rather than
  reusing Overview's `_sync_date_range_to_selected_account` (which sets
  `from_date = account.earliest_from_date`, i.e. full history).
- **Rationale**: An `/speckit-analyze` pass (2026-07-17) caught that an
  earlier draft of this plan implied the *entire* date-range sync
  mechanism was shared verbatim, which would have made Positions default
  to full account history instead of "YtD" (contradicting spec.md's
  FR-012/FR-014). The shortcut/clamp function itself is still fully
  shared (no duplication) — only the *choice of which shortcut code to
  apply automatically on account selection* differs per page: Positions
  always applies `SHORTCUT_YTD`, Overview applies none (it uses the
  account's raw earliest date directly, not via a shortcut code).
- **Alternatives considered**: Giving `build_account_date_controls()` or a
  shared sync function a `default_shortcut: str | None` parameter —
  rejected as unnecessary indirection for a single boolean-shaped
  difference between exactly two callers; each page's own account-change
  callback (already page-specific per research.md #1's ID-uniqueness
  discussion) simply calls a different one-line expression using the same
  shared `_shortcut_from_date` function.

## 2. Sharing the attribute-toggle control between Overview and Positions

- **Decision**: Extract `_attribute_toggle()` (currently private to
  `overview.py`) into a new shared module,
  `src/components/attribute_toggles.py`, as
  `build_attribute_toggle(attribute: AttributeDefinition, toggle_id_type:
  str, default_on: bool) -> html.Div` plus a
  `build_attribute_toggles(attributes, toggle_id_type, default_on_names) ->
  list[html.Div]` convenience wrapper. Both pages call the same builder
  with their own `toggle_id_type` string (`"overview-attribute-toggle"` /
  `"positions-attribute-toggle"`) so each page's own pattern-matching
  callback (`Input({"type": toggle_id_type, "name": ALL}, "value")`)
  remains independently scoped.
- **Rationale**: `portfolio-analysis-service`'s `AttributeDefinition`
  shape (`name`, `description`, `source`) is already identical between
  `GET /v1/timeseries/attributes` and `GET /v1/positions/attributes` (both
  verified against the respective OpenAPI contracts) — the existing
  `src/models/portfolio_analysis.py::AttributeDefinition` model is reused
  as-is for both, so the shared builder needs no new model, only a
  parameter for which pattern-matching `type` string each page's toggles
  should carry. This is the literal "configurable via API endpoint"
  refactor the spec calls for: each page's own client call supplies which
  endpoint's data feeds the shared, identical rendering function.
- **Alternatives considered**: A single global toggle-id-type shared by
  both pages — rejected: Overview and Positions can be on screen only one
  at a time (routed pages), but sharing one pattern-matching `type` string
  would make each page's callback also match the *other* page's
  (long-unmounted) toggle components in Dash's pattern-matching Input
  resolution in edge cases (e.g. during a fast route transition), which is
  an unnecessary and easily avoided coupling — a distinct `type` string per
  page costs nothing and removes the ambiguity entirely.

## 3. Position multi-select control (up to 50 entries, FR-005/FR-024)

- **Decision**: `dcc.Dropdown(id="positions-parameters-position-filter",
  multi=True, options=[...], searchable=True)` — a Dash core component
  already bundled with the existing `dash` dependency.
- **Rationale**: `dcc.Dropdown` with `multi=True` natively supports
  type-ahead filtering of its option list and renders selected items as
  removable pill/tag chips — exactly FR-024's "narrow the list by typing"
  requirement — with zero new dependency, satisfying constitution
  Principle V (prefer the standard library's built-in mechanism over a
  bespoke or third-party one). It comfortably handles 50 options; Dash's
  own component library and community usage patterns treat that as a
  small-to-medium option count, well under where a virtualized-list
  alternative would become necessary.
- **Alternatives considered**: A third-party virtualized multi-select
  (e.g. `dash-mantine-components`'s `MultiSelect`) — rejected: adds a new
  UI-kit dependency alongside the existing `dash-bootstrap-components` for
  a scale (50 items) `dcc.Dropdown` already handles natively, violating
  Principle V's "justify any bespoke/third-party addition" bar. A checklist
  of `dbc.Checkbox`es — rejected: not compact at 50 entries (FR-024
  explicitly asks for compact/efficient), and reinvents filtering
  `dcc.Dropdown` already provides.

## 4. Rendering a stacked area chart vs. a line chart (FR-007/FR-008)

- **Decision**: Both modes use the same `plotly.graph_objects.Scatter`
  trace type. Line mode (existing Overview behavior, reused) sets
  `mode="lines+markers"` with no `stackgroup`; stacked-area mode adds
  `stackgroup="positions"` (Plotly's native cumulative-stacking mechanism)
  and `mode="lines"` with `fill="tonexty"` implied by the shared
  `stackgroup`.
- **Rationale**: `stackgroup` is a first-class, built-in Plotly `Scatter`
  parameter purpose-built for exactly this (all traces sharing a
  `stackgroup` value are automatically cumulatively summed and area-filled
  in draw order) — no new chart type, trace class, or dependency, and it
  reuses the exact same data shape (`x`, `y` per position) the existing
  line-chart path already builds. This satisfies Principle V (use the
  library's own mechanism) the same way 017's `research.md` #1 already
  established as this project's precedent.
- **Alternatives considered**: `plotly.express.area()` — rejected: it's a
  convenience wrapper that constructs its own `go.Figure` from a long-form
  DataFrame, which would require reshaping the already-flat `entries` list
  into a DataFrame for no benefit over directly adding one parameter to the
  trace-building loop the line-chart path already has; introducing
  `pandas` as a new dependency for this alone is disproportionate (no other
  module in this codebase uses `pandas`).

## 5. Stable, high-contrast color assignment for up to 50 positions (FR-015, `/speckit-clarify` Q1 & Q3)

- **Decision**: A pure function,
  `_color_for_position(position_name: str) -> str`, that (a) hashes
  `position_name` with `hashlib.sha256` (not Python's built-in `hash()`)
  and takes the digest modulo a pre-generated palette size, then (b) looks
  up that index in a **pre-generated, fixed-order palette** of 50 colors
  built once at import time by stepping evenly around the HSL hue wheel
  (`colorsys.hls_to_rgb`, hue steps of `360/50` degrees, alternating
  lightness/saturation between two bands so adjacent hue-steps don't read
  as near-identical) and converting each to a hex string.
- **Rationale**: Must satisfy two spec requirements together: (1)
  deterministic/stable across process restarts, workers, and selection
  changes (`/speckit-clarify` Q3) — ruling out Python's built-in `hash()`,
  which is salted per-process (`PYTHONHASHSEED`) specifically to *not* be
  stable for strings; `hashlib.sha256` has no such salting. (2) High
  contrast/variability across up to 50 concurrent series (FR-015) — evenly
  spacing hues around the full color wheel (rather than picking from a
  small fixed named palette like Plotly's 24-color `Dark24`, which runs out
  before 50 and would force color reuse) guarantees a minimum hue
  separation between any two of the 50 pre-generated colors. Using stdlib
  `colorsys` + `hashlib` needs no new dependency (Principle V).
- **Alternatives considered**: Plotly's built-in qualitative palettes
  (`Dark24`, `Light24`, `Alphabet`) — rejected alone: the largest is 26
  colors, short of the 50-series requirement, and concatenating two
  different named palettes risks inconsistent contrast/lightness between
  the two halves; Python's built-in `hash()` for the position→index
  mapping — rejected: not stable across process restarts (breaks
  `/speckit-clarify` Q3's stability requirement) unless `PYTHONHASHSEED` is
  pinned process-wide, which is a deployment-configuration burden this
  feature shouldn't impose. Alphabetical-index-based assignment (1st
  selected position → color 1, 2nd → color 2, …) — rejected: this is
  exactly the "assigned by draw order" option `/speckit-clarify` Q3
  explicitly rejected, since a position's color would then shift whenever
  the position filter or account changes.

## 6. Rendering the comparison table with per-cell pastel shading (FR-017–FR-019)

- **Decision**: `dash.dash_table.DataTable` (bundled with the existing
  `dash` dependency, not a new package) with `style_data_conditional`
  entries computed per-row/per-column from the same fetched
  `PositionTimeSeriesResponse.entries`, rather than hand-built `dbc.Table`
  HTML with inline `style` props per cell.
- **Rationale**: `style_data_conditional` is `DataTable`'s built-in,
  purpose-made mechanism for exactly this — conditional per-cell
  background color based on a computed `filter_query` or row/column
  predicate — so the green/red/white shading rule (FR-019) is expressed
  declaratively against already-computed row data rather than manually
  interleaving Python `style` dict construction into hand-built `dbc.Table`
  row/cell markup. It ships with `dash` (already a dependency), so this is
  a zero-new-dependency choice consistent with Principle V, and it keeps
  the "which cell gets which color" logic in one declarative place instead
  of scattered across nested HTML-building loops.
- **Alternatives considered**: `dash_bootstrap_components.Table` built from
  a nested list of `html.Td` with inline `style={"backgroundColor": ...}` —
  rejected: `dbc.Table` has no first-class conditional-styling mechanism,
  so every cell's shading would need to be computed and threaded through
  manual HTML construction, more code for the same declarative outcome
  `DataTable.style_data_conditional` already provides.

## 6a. Attribute-aware value formatting on the chart and table (FR-008a)

- **Decision**: A single lookup-table function,
  `_format_attribute_value(attribute_name: str, value: float) -> str`, in
  `src/pages/_positions_chart.py`, used by both `_build_figure()` (axis
  tick format / hover template) and `_build_comparison_table()` (cell
  display values): currency style (`£`, thousands separator, 2 decimal
  places) for `market_value`/`income`/`book_cost`/`pnl`/`close_price`;
  plain numeric (no symbol, thousands separator) for `quantity`; currency
  as the fallback for any attribute name not in the lookup (matching
  `_overview_chart.py`'s existing `ATTRIBUTE_COLORS`/`DEFAULT_ATTRIBUTE_COLOR`
  fixed-mapping-with-default shape, since every currently known Positions
  attribute except `quantity` is monetary).
- **Rationale**: An `/speckit-analyze` pass (2026-07-17) found that
  Overview's own chart formatting (`_build_figure` in `_overview_chart.py`)
  hardcodes `£` currency formatting for every attribute, which is correct
  there because all five of Overview's own attributes are monetary — but
  Positions' attribute set additionally includes `quantity` (a share
  count), which FR-008's "match Overview's presentation style" would
  otherwise mis-format with a currency symbol. One shared formatting
  function used by both the chart and the table keeps the "which
  attributes are monetary" list in exactly one place, rather than
  duplicating it between figure-building and table-building code.
- **Alternatives considered**: Formatting only the table (leaving the
  chart's hover/axis text using Overview's un-adapted currency-only
  formatting) — rejected: the chart is just as user-facing as the table,
  and a `£1,234.00` hover label on a `quantity` line would be actively
  misleading, not merely inconsistent.

## 7. Existing test regression: `shell_parameters_bar_unchanged.feature`

- **Decision**: Update
  `tests/bdd/features/shell_parameters_bar_unchanged.feature` — remove
  `Positions` from the `Scenario Outline`'s `Examples` table (it no longer
  keeps the static 015-era placeholder bar once this feature ships), and
  add a new scenario mirroring the existing "The Overview route shows real
  controls, not the static placeholder" scenario, asserting the same for
  `/positions`.
- **Rationale**: That feature file currently encodes, as a regression
  guard, that `Positions` is one of the routes keeping 015's static,
  disabled placeholder bar (written when 016 first made Overview real and
  needed to prove it didn't affect the *other* routes). This feature makes
  `Positions` real by design (FR-002–FR-006), so that guard is now
  intentionally, correctly false for `/positions` — leaving it unchanged
  would make this feature's own implementation fail a legitimate existing
  test, not catch a real regression. `Performance` and `Income` remain in
  the outline unchanged, since neither is in this feature's scope.
- **Alternatives considered**: Leaving the feature file as-is and accepting
  the now-permanent failure — rejected outright: the constitution's
  Development Workflow requires passing tests before merge, and a stale
  assertion that's *supposed* to fail forever is not a meaningful test.
