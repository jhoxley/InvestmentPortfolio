# Phase 0 Research: Performance Page

## 1. Reusing existing response models for Performance data (no new models)

- **Decision**: `GET /v1/accounts/{account_name}/performance`'s response
  shape (`account_name`, `attributes: list[str]`, `from_date`, `to_date`,
  `entries: list[{date, ...measure values}]`, `_links`) is byte-for-byte
  identical to the existing `TimeSeriesResponse`/`TimeSeriesEntry` models
  already in `src/models/portfolio_analysis.py` (016). Likewise,
  `GET /v1/performance/attributes` returns the same `{name, description,
  source}` shape as `/v1/timeseries/attributes`/`/v1/positions/attributes`,
  already modeled as `AttributeDefinition`. No new Pydantic model is added
  for this feature — the new client methods (research.md #2) return the
  existing `TimeSeriesResponse` and `list[AttributeDefinition]` types.
- **Rationale**: Verified field-by-field against
  `portfolio-analysis-service/specs/007-performance-endpoints/contracts/openapi.yaml`
  (`PerformanceResponse`/`PerformanceEntry`/`PerformanceAttributeDefinition`
  schemas) — every field name and type matches an existing model exactly,
  including `TimeSeriesEntry`'s `extra="allow"` behavior already handling
  dynamic per-attribute keys (measure names like `"ITD (Ann.)"` are valid
  dict/extra-field keys even though they aren't valid Python identifiers;
  they are read via `.get()`/`model_dump()`, never dotted attribute access,
  the same way `overview.py` already reads `market_value` etc.). Adding a
  parallel `PerformanceResponse`/`PerformanceEntry`/
  `PerformanceAttributeDefinition` set would duplicate an identical shape
  for no behavioral difference, directly against constitution Principle V's
  "prefer standard/existing mechanisms over bespoke duplication" and SOLID
  guidance.
- **Alternatives considered**: New `PerformanceEntry`/`PerformanceResponse`
  classes for domain-name clarity — rejected: the shapes are structurally
  identical with no divergent field, so a new class would be a renamed copy
  requiring upkeep in two places if the upstream contract ever changes
  (e.g. adding a field), rather than one. A docstring on the new client
  methods documents that `TimeSeriesResponse` is being reused for
  Performance data, so the reuse is discoverable, not hidden.

## 2. New client methods (data-access only)

- **Decision**: Add `get_performance(account_name, attributes, start, end)
  -> TimeSeriesResponse` and `list_performance_attributes() ->
  list[AttributeDefinition]` to `PortfolioAnalysisClient` (Protocol) and
  `HttpPortfolioAnalysisClient`, calling `GET
  /v1/accounts/{account_name}/performance` and `GET
  /v1/performance/attributes` respectively — same shape as `get_timeseries`/
  `list_attributes`, reusing the same `_get()` helper and repeated-query-
  param convention (`[("attribute", a) for a in attributes]` +
  `start`/`end`).
- **Rationale**: Matches the existing pattern exactly (`get_timeseries`,
  `get_position_timeseries`) — one method per endpoint, Protocol +
  concrete-class pair, no new abstraction. Keeps all outbound HTTP access
  in the one existing data-access module (constitution Principle II).
- **Alternatives considered**: A single generic
  `get_timeseries_like(path, ...)` helper parameterized by URL path to
  serve both the account-timeseries and performance endpoints — rejected:
  the two existing sibling methods (`get_timeseries`,
  `get_position_timeseries`) already establish "one explicit method per
  endpoint" as this module's convention; introducing a generic wrapper for
  a third, still-distinct endpoint would be a speculative abstraction for a
  savings of a few lines, contradicting the "don't design for hypothetical
  future requirements" guidance and this module's own established shape.

## 3. The "ITD" shortcut button (spec Clarifications: relabel, not a new shortcut code)

- **Decision**: `src/components/date_range_controls.py::build_account_date_controls()`
  gains one new optional parameter, `first_shortcut_label: str = "YtD"`,
  changing only the **visible text** of the first shortcut button — its
  DOM id stays `overview-shortcut-ytd` (reused across all three routes,
  since only one route's parameters bar is ever mounted at a time,
  unchanged from research.md #1 in `018-positions-page`). No new
  `SHORTCUT_*` code is added. `performance.py` calls
  `build_account_date_controls(first_shortcut_label="ITD")` via a new
  `_build_performance_parameters_bar()` in `shell.py`. Performance's own
  page-local `_SHORTCUT_CODE_BY_BUTTON_ID` dict (mirroring
  `overview.py`/`positions.py`'s own copies) maps
  `"overview-shortcut-ytd"` to `SHORTCUT_ALL` (not `SHORTCUT_YTD`) — so
  clicking the button labeled "ITD" computes the account's full recorded
  history, identically to clicking the button labeled "All" right next to
  it. This deliberate redundancy (two buttons, one underlying
  computation) is the resolved behavior from spec.md's Clarifications.
- **Rationale**: The spec's own Clarifications session settled this
  exact ambiguity: keep all five buttons, relabel "YtD" to "ITD", accept
  that ITD and All compute the same date. Reusing the same button id with
  only a page-supplied label override is the minimal change consistent
  with `date_range_controls.py`'s existing "one shared implementation,
  each page supplies its own small piece of config" shape (`toggle_id_type`
  already works this way for `attribute_toggles.py`, research.md #2 in
  018). No behavioral divergence needs a new shortcut code — "ITD"'s
  *behavior* is exactly `SHORTCUT_ALL`'s existing computation, only the
  page-local click-handler mapping differs (already page-owned per
  018's own precedent of each page keeping its own
  `_SHORTCUT_CODE_BY_BUTTON_ID` copy).
- **Alternatives considered**: A new `SHORTCUT_ITD` code with its own
  entry in `_shortcut_from_date()` — rejected: it would compute exactly
  the same date as the existing `SHORTCUT_ALL` branch, making it a
  duplicate branch, not a new behavior; the spec's resolution only
  requires a different **label**, not a different **computation**.
  Making the whole shortcut button row page-configurable (a list of
  `(id, label, code)` tuples passed in by the caller) — rejected as
  over-generalizing for a single-label difference across exactly three
  callers; the one optional parameter is simpler and the two unaffected
  callers (`overview.py`, `positions.py`) need no change at all.

## 4. Default date range on load/account-switch: full history, not "YtD"

- **Decision**: The Performance page's account-switch handler (mirroring
  `overview.py::_sync_date_range_to_selected_account`) uses the account's
  own `_earliest_from_date()` directly (full recorded history) as the
  default "From" date — the same default Overview itself uses, not
  Positions' own "always YtD" default.
- **Rationale**: spec.md's FR-008/FR-009 define the Performance page's own
  default as "ITD" (full history), consistent with "ITD" being both the
  page's primary shortcut label and the natural default lens for a
  returns-over-time page. This mirrors Overview's existing
  `_sync_date_range_to_selected_account` function's behavior exactly
  (full history via `_earliest_from_date`), so no new date-computation
  function is needed — only a new page-local wrapper callback with the
  same body shape (matching precedent: `positions.py` already has its own
  distinct account-switch callback body instead of literally importing
  Overview's, per 018 research.md #1a).
- **Alternatives considered**: Reusing Positions' "always YtD" default —
  rejected outright; the spec explicitly calls for full-history as this
  page's default, matching "ITD," not "YtD."

## 5. Default measure toggled on first load: first attribute returned, not hard-coded

- **Decision**: Unlike Overview's `_DEFAULT_METRIC = "market_value"`
  (a name known in advance), Performance's default toggle is computed at
  fetch time from whichever measure the metadata endpoint returns first:
  `frozenset({attributes[0].name})` if the fetched list is non-empty, else
  `frozenset()`. Passed as `default_on_names` to the existing
  `build_attribute_toggles()` (reused verbatim, research.md #2 in
  018-positions-page), with its own `toggle_id_type="performance-attribute-toggle"`.
- **Rationale**: The measure set (`ITD`, `ITD (Ann.)`, `1Y`, `3Y`, `5Y`) is
  API-driven, not a fixed client-side constant (constitution Principle I —
  the client must not hard-code business-domain values it doesn't own).
  The upstream contract's own example response and metadata ordering lists
  `ITD` first, so this resolves to "ITD" toggled on by default in
  practice, without the client asserting that name as a literal constant.
- **Alternatives considered**: Hard-coding `_DEFAULT_MEASURE = "ITD"` like
  Overview's `_DEFAULT_METRIC` — rejected: unlike `market_value` (a stable,
  long-standing account-level attribute name), asserting a literal "ITD"
  string couples this page to the upstream metadata's current ordering/
  naming without the safety net of falling back gracefully if it ever
  changes; "first attribute returned" is a one-line equivalent that stays
  correct either way.

## 6. Percentage formatting for the chart (new, distinct from Overview/Positions' currency formatting)

- **Decision**: A new pure-function module,
  `src/pages/_performance_chart.py`, mirrors `_overview_chart.py::_build_figure`
  exactly (one `go.Scatter` trace per toggled-on measure, `mode="lines+markers"`,
  horizontal legend, `hovermode="x unified"`) but formats the y-axis and
  hover template as a percentage (`yaxis.tickformat=".1%"`,
  `hovertemplate=...+"%{y:.1%}"`) instead of GBP currency, and uses its own
  fixed measure→color mapping (`PERFORMANCE_ATTRIBUTE_COLORS`, keyed by
  `"ITD"`/`"ITD (Ann.)"`/`"1Y"`/`"3Y"`/`"5Y"`, same
  fixed-mapping-with-default shape as `_overview_chart.py`'s
  `ATTRIBUTE_COLORS`/`DEFAULT_ATTRIBUTE_COLOR`).
- **Rationale**: Plotly's `go.Scatter`/`Layout` `tickformat`/hover format
  strings support d3-format percentage specifiers (`".1%"`) natively — no
  new dependency, satisfying constitution Principle V. Performance measures
  are return rates (e.g. `0.183` meaning 18.3%), not monetary amounts, so
  reusing Overview's `£`-prefixed currency formatting verbatim would
  mislabel every value; a distinct small module (mirroring, not sharing,
  `_overview_chart.py`) keeps this formatting difference isolated the same
  way `_positions_chart.py` already isolates its own attribute-aware
  formatting (018 research.md #6a) rather than retrofitting conditional
  logic into the Overview-owned module.
- **Alternatives considered**: Adding a `value_format: Literal["currency",
  "percentage"]` parameter to `_overview_chart.py::_build_figure` and
  reusing it directly — rejected: `_overview_chart.py` is Overview-owned
  (its module docstring already says so) and this feature's own value
  formatting, color palette, and title text are all different enough
  (three of `_build_figure`'s ~6 configurable pieces) that parameterizing
  the existing function would leave more conditional/unused-branch surface
  than a small, independent ~40-line module mirroring its structure.

## 7. No comparison table, no stacked-area toggle (spec Clarifications — restated for traceability)

- **Decision**: `performance.py` has no data table, no multi-select
  filter, and no chart-mode toggle — layout mirrors `overview.py`'s
  account-level chart section only (mount-trigger, stores, attribute
  toggles container, one `dcc.Loading`-wrapped chart container), not
  `positions.py`'s additional table/filter/toggle machinery.
- **Rationale**: Already resolved in spec.md's Clarifications session
  (2026-07-30): the chart and its controls are this feature's entire
  scope. Restated here only so `tasks.md` generation has an explicit,
  plan-level "do not add" anchor alongside the FR list.
- **Alternatives considered**: N/A — already decided at the spec level;
  no new alternatives evaluated during planning.

## 8. Existing regression test: `shell_parameters_bar_unchanged.feature`

- **Decision**: Update
  `tests/bdd/features/shell_parameters_bar_unchanged.feature` — remove
  `Performance` from the `Scenario Outline`'s `Examples` table (it no
  longer keeps the static, disabled 015-era placeholder bar once this
  feature ships), and add a new scenario mirroring the existing "The
  Positions route shows real controls, not the static placeholder"
  scenario, asserting the same for `/performance`. `Income` remains in the
  outline unchanged (out of scope for this feature).
- **Rationale**: Directly mirrors `018-positions-page`'s own research.md
  #7 — this file encodes, as a regression guard, which routes still keep
  015's static placeholder bar; Performance becoming real by design
  (FR-002–FR-006) makes the existing guard intentionally, correctly false
  for `/performance`, so it must be updated rather than left to fail
  permanently.
- **Alternatives considered**: Leaving the feature file as-is — rejected:
  the constitution's Development Workflow requires passing tests before
  merge, and a stale assertion supposed to fail forever is not a
  meaningful test (same conclusion 018 already reached).
