# Phase 0 Research: Account Performance Chart on Overview

All items below were resolved during planning (no outstanding
`NEEDS CLARIFICATION` markers in Technical Context). Each follows
Decision / Rationale / Alternatives considered.

## 1. HTTP client for calling `portfolio-analysis-service`

- **Decision**: `httpx.Client`, wrapped behind a `Protocol` +
  `HttpPortfolioAnalysisClient` concrete class in
  `src/services/portfolio_analysis_client.py`.
- **Rationale**: `portfolio-analysis-service` already calls
  `market-data-web-service` this exact way
  (`app/clients/market_data_client.py`) — same `httpx.Client(base_url=...,
  timeout=...)`, same `Protocol` abstraction for testability, same
  `raise_for_status()` + typed-exception-on-`httpx.HTTPError` handling.
  Reusing the proven pattern keeps the monorepo's client code consistent and
  gives a directly-applicable test strategy (see #6).
- **Alternatives considered**: `requests` (no async story, no precedent in
  this monorepo — would introduce a second HTTP library for no benefit,
  violating Principle V's "prefer established, already-adopted libraries");
  raw `urllib` (rejected — reinvents error handling/timeouts that `httpx`
  already solves).

## 2. Charting

- **Decision**: `dcc.Graph` rendering a `plotly.graph_objects.Figure` built
  from one `go.Scatter` trace per toggled-on metric.
- **Rationale**: `plotly` (6.9.0) is already installed transitively as a
  Dash dependency — no new package needed, only a new *direct* import. Dash
  and Plotly are built for each other (native hover-tooltip support via
  `hovermode="x unified"`/per-trace `hovertemplate`, native legend
  positioning via `layout.legend`, hover-over date/series/value out of the
  box) — satisfying FR-011 (hover tooltip) and FR-010 (legend below chart)
  with configuration, not custom code.
- **Alternatives considered**: `dash-bio`/`dash-charts` wrappers (rejected —
  unnecessary extra dependency for a plain line chart); hand-rolled SVG/D3
  via a custom component (rejected outright — Principle V explicitly calls
  out charting as a "solved problem" to not reimplement).

## 3. Date range controls

- **Decision**: Two `dcc.DatePickerSingle` instances (`from`, `to`), not a
  single `dcc.DatePickerRange`.
- **Rationale**: The spec (FR-002) describes "two date pickers UI elements,
  a 'from' and 'to'" as independently-addressable controls, and each has a
  distinct, differently-sourced default (FR-003 from the account payload,
  FR-004 computed as last business day) — two single-pickers map directly
  and let each carry its own `min_date_allowed`/`max_date_allowed`
  constraint (FR-015: no "to" after today, no "from" after "to") without
  the extra range-relationship logic `DatePickerRange` would otherwise
  encapsulate and then have to be partially overridden.
- **Alternatives considered**: `dcc.DatePickerRange` (rejected per above —
  fights the spec's two-independent-controls framing); free-text date
  inputs (rejected — no built-in calendar affordance/validation, worse UX
  for a "bold, clear, professional" financial dashboard per FR-012).

## 4. Metric toggle controls

- **Decision**: `dbc.Checklist` (switch-styled, `switch=True`) with one
  `dbc.Tooltip` per option, targeting each option's generated `id`.
- **Rationale**: Renders one on/off control per attribute from
  `/v1/timeseries/attributes`, satisfies FR-005/FR-006 (independent toggle +
  hover tooltip of the attribute's `description`) using existing
  `dash-bootstrap-components` primitives already used elsewhere in the shell
  (`sidebar.py`, `shell.py`) — no new dependency, consistent visual language.
- **Alternatives considered**: Individual `dbc.Switch` components in a loop
  (viable, slightly more verbose — `dbc.Checklist` with `switch=True`
  achieves the same rendering with less boilerplate and a single callback
  `Input` instead of N).

## 5. Structured logging on the new outbound calls

- **Decision**: Adopt `structlog`, bound with `account_name`/date-range
  context, matching `market_data_client.py`'s
  `logger.bind(...)` → `log.info(...)`/`log.error(...)` shape.
- **Rationale**: Both backing services already standardize on `structlog`
  for outbound-call logging (request/duration/error fields). This feature
  is the browser's first outbound HTTP integration; adopting the same
  convention now avoids a second logging idiom entering the codebase later
  and gives operators consistent log shapes across all three services.
- **Alternatives considered**: stdlib `logging` (rejected — would be a
  second logging convention alongside the monorepo's established
  `structlog` usage, for a UI layer that will only grow more outbound calls
  over time).

## 6. Testing the new HTTP client

- **Decision**: `httpx.MockTransport` injected via the client's existing
  `transport: httpx.BaseTransport | None` constructor parameter (same
  parameter shape as `HttpMarketDataClient`) — no new test dependency.
- **Rationale**: Directly mirrors the pattern already exercised in
  `portfolio-analysis-service`'s own client tests; keeps BDD steps and unit
  tests fast/hermetic without a real running `portfolio-analysis-service`
  instance, and without adding `respx`/`requests-mock` when `httpx` already
  ships the tool needed.
- **Alternatives considered**: Spinning up a real (or `TestClient`-backed)
  `portfolio-analysis-service` instance for BDD runs (rejected — slower,
  cross-repo test coupling, and unnecessary given `MockTransport` fully
  covers request/response shape verification); `respx` (rejected — extra
  dependency solving a problem `httpx.MockTransport` already solves).

## 7. Route-aware shared parameters bar vs. fully page-scoped controls

- **Decision**: The existing shared `app-parameters-bar` (in
  `src/layout/shell.py`, built in 015 as a static disabled placeholder) is
  made route-aware: a callback keyed on `dcc.Location.pathname` swaps its
  children — real Account/From/To controls when `pathname == "/"`
  (Overview), the existing static disabled placeholder unchanged on every
  other route. The attribute metric-toggle panel (Overview-only per FR-007)
  is *not* placed in the shared bar; it lives inside
  `src/pages/overview.py`'s own page layout (inside `dash.page_container`),
  so it structurally cannot appear on other pages — no visibility logic
  needed for it at all.
- **Rationale**: 015 established "content area top always shows a
  parameters placeholder" as persistent shell behavior across *all* pages;
  016 must not regress that for Performance/Positions/Income (out of scope
  here) while making Overview's version real. Splitting the two concerns —
  route-aware shared bar for Account/date (present everywhere, real only on
  Overview) vs. page-owned panel for metric toggles (present only where the
  page itself renders it) — satisfies FR-007's "MUST NOT appear on any other
  navigation section" by construction rather than by an extra
  show/hide condition to keep in sync.
- **Alternatives considered**: Moving Account/date controls into the
  Overview page too, leaving the shared bar untouched (rejected — spec's
  Account/date FRs don't scope those controls to "Overview only" the way
  FR-007 explicitly scopes the toggles, and duplicating a second
  disabled-looking Account/date bar above a real one would contradict
  FR-012's "bold, clear, professional" requirement); making the whole shared
  bar always show all Overview controls on every page, disabled elsewhere
  (rejected — would require fetching Overview-only data like attributes on
  pages that don't need it, and contradicts FR-007 outright for the toggles).

## 8. Client-side date computations (non-financial, Principle I-compliant)

- **Decision**: "Last completed business day" (FR-004) and "earliest
  `from_date` across `capital_ledger`/`position_ladder`" (FR-003) are
  computed in a small pure function in
  `tests/unit/test_overview_chart_shaping.py`'s corresponding module
  (`src/pages/overview.py` or a `_selectors.py` helper), using Python's
  stdlib `datetime`/`date.weekday()` — no calendar/holiday dependency, per
  the spec's own Assumption ("standard Monday-Friday business-day
  definition with no public-holiday calendar").
- **Rationale**: These are UI *selection* computations (which date to
  default a picker to), not financial calculations — explicitly the kind of
  "purely presentational transform" the constitution's Principle I permits
  client-side. No new dependency needed since stdlib `date.weekday()`
  (0=Monday..6=Sunday) fully covers the "no weekend" rule.
- **Alternatives considered**: A holiday-aware business-day library (e.g.
  `pandas`/`numpy` business-day offsets, or `workalendar`) — rejected, spec
  explicitly excludes a public-holiday calendar; pulling in `pandas` for one
  weekday check would be a disproportionate new dependency.

## 9. Caching the `/v1/accounts` and `/v1/timeseries/attributes` payloads across interactions

- **Decision**: Both payloads are fetched once per page load (on Overview
  mount) into `dcc.Store` (`session` storage type is unnecessary — plain
  in-memory `dcc.Store` scoped to the page is sufficient since Dash's
  server-rendered callback graph re-mounts it on navigation), then reused by
  downstream callbacks (account switch re-reads the already-fetched accounts
  list to recompute from/to defaults; metric toggles re-read the
  already-fetched attributes list) — only the timeseries endpoint is called
  again per account/date/metric change.
- **Rationale**: Avoids redundant network calls on every date-range tweak or
  metric toggle (`/v1/accounts` and `/v1/timeseries/attributes` don't change
  based on those interactions), keeping the 100ms loading-feedback budget
  achievable and reducing load on `portfolio-analysis-service`.
- **Alternatives considered**: Re-fetching accounts/attributes on every
  callback (rejected — wasteful, and no functional requirement needs
  live-refresh of account/attribute metadata within a single page session).
