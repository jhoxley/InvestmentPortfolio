---
description: "Task list for Value at Risk View (Risk Page)"
---

# Tasks: Value at Risk View (Risk Page)

**Input**: Design documents from `specs/026-var-risk-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED — the constitution's Principle III (Test-First BDD) is
non-negotiable. Every test task must be run and seen **failing** before its implementation task.

**Organization**: Grouped by user story (P1–P3 from spec.md). All paths are relative to
`portfolio-browser/`.

**Ordering note**: Models, the client methods, the tab shell/stores, the controls block, and both
fetch callbacks are shared by every user story (nothing renders without fetched data and a place
to put it), so they ship in Foundational rather than being duplicated into US1. The single
`_render_var_view` callback (Dash forbids two callbacks targeting the same Output) is *introduced*
by US1 (the chart half) and *extended* by US2 (the panel half) and US5 (the empty/stale branches)
— each extension is its own task so the story that needs it is the one credited with writing it,
mirroring feature 025's own "ordering note" precedent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6

---

## Phase 1: Setup

**No tasks required.** No new dependency, config key, or environment setting — `dbc.Tabs`,
`plotly.subplots.make_subplots`, and `concurrent.futures.ThreadPoolExecutor` are all already
available in this project's pinned dependencies / the stdlib.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Everything every user story needs before it can render anything: the new response
models, the new client methods, the tab shell, the controls block, and the two fetch callbacks
that populate `risk-var-store`/`risk-var-methods-store`.

- [X] T001 Write failing unit tests in `tests/unit/test_portfolio_analysis_models.py` for every
  new model in data-model.md: `DateRange`, `VarStatusSummary` (validate against a *full* 012
  `VarStatus`-shaped fixture dict that also includes `stale_dates_last_run`, `pending_outcomes`,
  `last_run`, `instruments`, `warnings` — assert those extra fields are silently ignored, and
  separately assert `computed_range: null` validates to `None`), `ConfidenceLevelEstimate`,
  `VarSeriesEntry`, `VarSeriesResponse` (validate against a full 013 series response fixture,
  asserting the `_links` alias round-trips via `model_dump(mode="json")`), `RollingExceptionPoint`,
  `BacktestConfidenceResult`, `VarBacktestResponse` (full 013 backtest response fixture, including
  a null `zone`/`rolling_exceptions` case), `MethodLookback`, `VarMethodsResponse` (full 013
  methods response fixture). Run and confirm every new test fails (`ImportError`/`AttributeError`
  — the models don't exist yet).
- [X] T002 Add all ten models from T001 to `src/models/portfolio_analysis.py` exactly per
  data-model.md (field names, types, the `_links` alias pattern already used by
  `ReturnHistogramResponse`). Confirm T001 passes.
- [X] T003 Write failing unit tests in `tests/unit/test_portfolio_analysis_client.py` for
  `get_var_series(account_name, start, end, lookback)`, `get_var_backtest(account_name, start, end,
  lookback, pnl_basis, min_quality)`, `get_var_methods()`, and `get_var_status(account_name)`,
  mirroring `get_return_histogram`'s own test pattern (httpx.MockTransport asserting the request
  path/query params, successful-response parsing into the T002 models, and
  `PortfolioAnalysisServiceError` on a non-2xx/timeout/connection error). Explicitly assert that
  `get_var_series`'s and `get_var_backtest`'s requests **never** include a `confidence` query
  parameter (research.md #1 — always omitted so the server returns every configured level).
  `get_var_methods` and `get_var_status` take no look-back/date/confidence parameters. Run and
  confirm every new test fails.
- [X] T004 Add the four methods from T003 to both `PortfolioAnalysisClient` (the `Protocol`) and
  `HttpPortfolioAnalysisClient` in `src/services/portfolio_analysis_client.py`. Confirm T003
  passes.
- [X] T005 [P] Write failing unit tests in `tests/unit/test_var_controls.py` for a pure
  `build_controls(methods: VarMethodsResponse | None) -> html.Div` in a new
  `src/pages/_var_controls.py`: with `methods=None`, renders a disabled/placeholder block (no
  options yet); with a populated `VarMethodsResponse`, renders — each with a stable, documented
  DOM id — a confidence-level multi-select whose option *labels* are percentage strings via
  `f"{bp / 100:g}%"` (research.md #5: `9500`→`"95%"`, `9750`→`"97.5%"`, `9900`→`"99%"`) and
  *values* are the raw basis-point integers, defaulting to every level selected (FR-003); a
  look-back select whose options come from `methods.lookbacks` and whose default value is the
  entry with `is_headline=True`; a units toggle (money/percentage, default money); a PnL-basis
  toggle (hypothetical/ladder, default hypothetical, matching 013's own default); a "hide
  degraded-quality dates" toggle (default off); a "show Expected Shortfall" toggle (default off,
  FR-007). Run and confirm every new test fails.
- [X] T006 Create `src/pages/_var_controls.py` implementing `build_controls()` per T005. Confirm
  T005 passes.
- [X] T007 Write a failing BDD scenario in a new `tests/bdd/features/var_risk_tab_shell.feature`
  and a new `tests/bdd/steps/test_var_risk_steps.py` (following `test_risk_steps.py`'s
  `dash_duo`/fake-client monkeypatch pattern): "Given I am on the Risk page, Then there is a
  'Value at Risk' tab next to the histogram tab; When I select it, Then the shared account
  selector, date range and shortcut buttons remain the same DOM elements (not duplicated) as on
  the histogram tab." Run and confirm it fails (the tab doesn't exist).
- [X] T008 In `src/pages/risk.py`, wrap the existing histogram row in a `dbc.Tab(label="Return
  Histogram", tab_id="risk-tab-histogram")` and add a second, initially-placeholder
  `dbc.Tab(label="Value at Risk", tab_id="risk-tab-var")` inside a new `dbc.Tabs(id="risk-tabs")`,
  per contracts/ui-contract.md's Layout section. Add `dcc.Store(id="risk-var-store")`,
  `dcc.Store(id="risk-var-methods-store")`, and containers for the controls block, the stale
  banner, the chart, and the backtest panel inside the new tab's children. The shared
  account/date/shortcut controls stay in `shell.py`'s parameters bar, untouched. Confirm T007
  passes.
- [X] T009 Write failing unit tests in `tests/unit/test_var_risk_page.py` (new file, mirroring
  `test_risk_page.py`'s plain-function-call pattern) for the `_fetch_var_methods` callback
  function: given a fake client's `get_var_methods()` return value, asserts it writes to both
  `risk-var-methods-store.data` and the controls container's `children` (via
  `_var_controls.build_controls`); given a client that raises `PortfolioAnalysisServiceError`,
  asserts the controls container instead shows an error state and the store is not updated with
  partial data. Run and confirm it fails.
- [X] T010 Wire the `_fetch_var_methods` callback in `src/pages/risk.py`:
  `Input("risk-mount-trigger", "n_intervals")` → `client.get_var_methods()` →
  `risk-var-methods-store.data` + controls container, per ui-contract.md #1. Confirm T009 passes.
- [X] T011 Write failing unit tests in `test_var_risk_page.py` for the `_fetch_var_data` callback
  function: given a fake client, asserts it calls `get_var_series` once, `get_var_backtest` four
  times (once per `(pnl_basis, min_quality)` pair — assert all four distinct combinations are
  requested), and `get_var_status` once, all **concurrently** (assert via a fake client that
  records call-start/call-end timestamps that the four backtest calls' windows overlap, not that
  they run strictly sequentially); asserts the combined payload written to `risk-var-store.data`
  matches data-model.md's shape; asserts that if *any* of the six calls raises
  `PortfolioAnalysisServiceError`, the store is written with `fetch_error` set and no partial
  data. Run and confirm every new test fails.
- [X] T012 Wire the `_fetch_var_data` callback in `src/pages/risk.py`:
  `Input("app-parameters-account", "value")`, `Input("app-parameters-from-date", "date")`,
  `Input("app-parameters-to-date", "date")`, `Input("risk-var-lookback", "value")` → a
  `concurrent.futures.ThreadPoolExecutor` dispatching the six calls (research.md #6) →
  `risk-var-store.data`, per ui-contract.md #2. `running=[...]` disables the shared account/date/
  shortcut controls and the look-back select during the fetch. Confirm T011 passes.

**Checkpoint**: The tab exists, shares controls correctly, and populates both stores on mount/
account/date/look-back changes. No chart or panel renders yet — that is US1/US2.

---

## Phase 3: User Story 1 - See Daily Risk Against Realised Outcomes (Priority: P1) 🎯 MVP

**Goal**: The main chart — PnL bars with a VaR overlay, exceedances highlighted, optional ES —
renders from the data Foundational already fetches.

**Independent Test**: Open the tab for an account with a completed calculation; see bars + an
overlay line; see an exceedance day visually distinguished; toggle "show ES" and see a second
overlay.

### Tests for User Story 1 (write first, must fail)

- [X] T013 [P] [US1] Write failing unit tests in `tests/unit/test_var_chart.py` for a pure
  `build_figures(series: list[VarSeriesEntry], selected_confidence_bp: list[int], units: str,
  pnl_basis: str, hide_degraded: bool, show_es: bool) -> go.Figure` in a new
  `src/pages/_var_chart.py`: one bar per entry, `x=outcome_date`, `y` taken from the selected
  `pnl_basis`'s field (`hypothetical_pnl_gbp`/`ladder_pnl_gbp`), skipping entries where that field
  is `None` (pending outcome, per spec.md Edge Cases); one overlay line per `confidence_bp` in
  `selected_confidence_bp`, `y` = the negative of that level's `var_gbp`/`var_pct` depending on
  `units`, with a gap (no point) where that level's value is `None` (insufficient quality); any
  bar whose selected-basis exception flag is `True` for *any* selected level rendered in the
  exceedance color (a named constant, not inline); a second, shared-x-axis subplot
  (`make_subplots(shared_xaxes=True)`, research.md #3) carrying `total_value_gbp` and
  `proxied_mv_pct`/`rescaled_mv_pct`. Run and confirm every new test fails.
- [X] T014 [P] [US1] Write failing BDD scenarios in a new `tests/bdd/features/var_risk_chart.feature`
  (steps in `test_var_risk_steps.py`) for spec.md US1's four acceptance scenarios: the tab/shared
  controls scenario (may reuse T007's scenario by tag rather than duplicating), bars+overlay
  render, an exceedance day is visually distinguished, and the ES toggle adds a second overlay.
  Include one scenario (SC-001) asserting that on first load the main chart, the linked
  market-value chart, *and* the backtest panel are all present together — not just the main
  chart. Run and confirm they fail.

### Implementation for User Story 1

- [X] T015 [US1] Create `src/pages/_var_chart.py` implementing `build_figures()` per T013. Confirm
  T013 passes.
- [X] T016 [US1] Wire the `_render_var_view` callback in `src/pages/risk.py`:
  `Input("risk-var-store", "data")` plus the confidence/units/PnL-basis/hide-degraded/show-ES
  controls (no look-back — that is a refetch trigger, not an instant one) → calls
  `_var_chart.build_figures(...)` and sets the chart `dcc.Graph`'s `figure`; the panel output is
  set to a simple loading placeholder for now (US2 replaces it). This callback must not call the
  client at all (FR-010) — no `_get_client()`/`get_var_*` call anywhere in its body. Confirm
  T014 passes.
- [X] T017 [US1] Run `python -m pytest tests/unit/test_var_chart.py -q` and the US1 BDD scenarios;
  confirm green.

**Checkpoint**: Opening the Value at Risk tab for an account with completed data shows the chart
with a correct VaR overlay and exceedance highlighting. This alone is a demoable MVP.

---

## Phase 4: User Story 2 - Judge Whether the Model Can Be Trusted (Priority: P1)

**Goal**: The backtest panel renders alongside the chart, reading the already-fetched
`(pnl_basis, min_quality)` result matching the current controls.

**Independent Test**: With the chart showing, verify the panel reports exceedances-vs-expected,
both p-values, the traffic-light zone, mean VaR and VaR stability for the selected confidence
level(s) and the same range as the chart.

### Tests for User Story 2 (write first, must fail)

- [X] T018 [P] [US2] Write failing unit tests in `tests/unit/test_var_backtest_panel.py` for a
  pure `build_panel(backtest_by_basis_quality: dict, selected_confidence_bp: list[int], pnl_basis:
  str, hide_degraded: bool) -> html.Div` in a new `src/pages/_var_backtest_panel.py`: selects
  `backtest_by_basis_quality[pnl_basis][("ok" if hide_degraded else "degraded")]`; renders, per
  selected confidence level, `exception_count`/`expected_exceptions`, `kupiec_p_value`,
  `conditional_coverage_p_value`, a pass/fail-style badge from `zone` (e.g. green/yellow zone →
  "pass"-style, red → "fail"-style — a named mapping, not inline per-call logic), `mean_var_gbp`
  (always money — the API has no percentage equivalent, and the units toggle does not affect this
  figure, per spec.md's Assumptions), and `var_stability`; when `observation_count < 2`, shows "not enough
  observations" for `var_stability` and the LR/p-value fields instead of `None`/`NaN`. Run and
  confirm every new test fails.
- [X] T019 [P] [US2] Write failing BDD scenarios in a new
  `tests/bdd/features/var_risk_backtest_panel.feature` for spec.md US2's two acceptance scenarios.
  Run and confirm they fail.

### Implementation for User Story 2

- [X] T020 [US2] Create `src/pages/_var_backtest_panel.py` implementing `build_panel()` per T018.
  Confirm T018 passes.
- [X] T021 [US2] Extend the `_render_var_view` callback (T016) to replace its panel placeholder
  with a real call to `_var_backtest_panel.build_panel(...)`, selecting the fetched
  `(pnl_basis, min_quality)` pair exactly as T018 specifies (research.md #1/#4). Still no client
  call in this callback's body. Confirm T019 passes.
- [X] T022 [US2] Run `python -m pytest tests/unit/test_var_backtest_panel.py -q` and the US2 BDD
  scenarios; confirm green.

**Checkpoint**: Chart and panel both render from one fetch; US1+US2 together deliver the view's
full core value.

---

## Phase 5: User Story 3 - Explore Confidence Levels, Units and PnL Basis Instantly (Priority: P2)

**Goal**: Prove, not just assume, that the four "instant" controls never trigger a new request.

**Independent Test**: With the tab loaded, toggle confidence/units/PnL-basis one at a time and
confirm the chart/panel update with zero additional client calls.

### Tests for User Story 3 (write first, must fail)

- [X] T023 [P] [US3] Write failing BDD scenarios in a new
  `tests/bdd/features/var_risk_instant_controls.feature` for spec.md US3's three acceptance
  scenarios, using a fake client that records a call count (mirroring how other pages' BDD tests
  assert fetch behaviour) — each scenario asserts the call count is unchanged after the toggle.
  Run and confirm they fail (fails trivially until T016/T021 exist, then must still fail if any
  toggle wrongly triggers the fetch callback instead of only the render callback).
- [X] T024 [P] [US3] Write a failing unit test in `tests/unit/test_var_controls.py` (or a new
  callback-level test in `tests/unit/test_var_risk_page.py` if the guard is implemented as a
  callback rather than inside `build_controls()` itself) for FR-003's "always retain at least one
  selected level" guard: given the confidence multi-select currently holding exactly one value,
  simulate a change event that would clear it to an empty list, and assert the resulting value is
  reverted to the single previously-selected level rather than becoming empty. Run and confirm it
  fails.

### Implementation for User Story 3

- [X] T025 [US3] Implement the guard from T024: a small callback (or, if feasible without a
  separate `Input`/`State` round-trip, client-side logic in `_var_controls.py`) that intercepts an
  attempted clear-to-empty on the confidence multi-select and restores the last-selected value.
  Confirm T024 passes.
- [X] T026 [US3] Audit `_render_var_view`'s (T016/T021) `Input` list and body: confirm
  confidence/units/PnL-basis/hide-degraded/show-ES are `Input`s only to the render callback (never
  to `_fetch_var_data`, T012), and confirm the render callback's body contains no `_get_client()`
  or `get_var_*` call. Fix either callback's wiring if T023 reveals a gap. Confirm T023 passes.
- [X] T027 [US3] Run the US3 BDD scenarios and T024's unit test; confirm green.

**Checkpoint**: The three "instant" controls are now BDD-proven network-free, not just assumed so
by construction.

---

## Phase 6: User Story 4 - Change Account, Dates or Look-back (Priority: P2)

**Goal**: Prove account/date/look-back changes do refetch, and that no periodicity control leaks
into this view.

**Independent Test**: Change account, then date range, then look-back; each triggers a fresh fetch
and a refreshed chart/panel. No periodicity control is visible.

### Tests for User Story 4 (write first, must fail)

- [X] T028 [P] [US4] Write failing BDD scenarios in a new
  `tests/bdd/features/var_risk_refetch_controls.feature` for spec.md US4's four acceptance
  scenarios (account/date/look-back each refetch; no periodicity control present/effective on
  this tab). For at least one refetch scenario (SC-006), assert the *previous* selection's data
  (e.g. a bar/overlay value unique to the first account/range) is no longer present once the new
  data has rendered, not merely that new data appears alongside it. Run and confirm they fail.

### Implementation for User Story 4

- [X] T029 [US4] Confirm the look-back select built by `_var_controls.build_controls()` (T006) is
  wired as an `Input` to `_fetch_var_data` (T012) — it should already be, per T012's own
  description; add it now if it was missed. Confirm no `build_periodicity_control(...)` call (or
  equivalent) is reachable from the Value at Risk tab's children. Confirm T028 passes.
- [X] T030 [US4] Run the US4 BDD scenarios; confirm green.

**Checkpoint**: Full account/date/look-back navigation parity with every other page, confirmed by
BDD rather than assumed from Foundational's wiring.

---

## Phase 7: User Story 5 - Understand Missing or Stale Risk Data (Priority: P2)

**Goal**: An account with no calculated risk data gets an explanatory empty state instead of a
blank/broken chart; an account whose risk data lags its ladder gets a missing-dates banner.

**Independent Test**: Open the tab for an account with no VaR run — see an empty state, no chart/
panel. Open it for an account whose `missing_dates > 0` — see the banner and a still-rendering
chart/panel.

### Tests for User Story 5 (write first, must fail)

- [X] T031 [P] [US5] Write failing unit tests in `tests/unit/test_var_risk_page.py` for the
  empty/stale branching logic ui-contract.md's "Empty / error states" section describes:
  `fetch_error` set → empty state with guidance text; `computed_range is None` → the same empty
  state; `computed_range` set but the series list for the resolved range is empty → the narrower
  "No data for the selected range" message; otherwise → the normal chart/panel render path is
  taken (delegate to T015/T020's builders). Run and confirm every new test fails.
- [X] T032 [P] [US5] Write failing BDD scenarios in a new
  `tests/bdd/features/var_risk_empty_and_stale.feature` for spec.md US5's two acceptance
  scenarios. For the staleness scenario (SC-005), assert the banner's rendered number equals the
  fake client's configured `missing_dates` value *exactly* (e.g. configure it to a distinctive
  number like 7 and assert that literal number appears), not just that some banner text appears.
  Run and confirm they fail.

### Implementation for User Story 5

- [X] T033 [US5] Extend `_render_var_view` (T016/T021) with the branching from T031, replacing the
  chart/panel outputs with the appropriate empty-state `html.Div` (reusing `risk.py`'s existing
  `_empty_state`/`_error_state` helpers) in the `fetch_error`/no-data cases. Confirm T031 passes.
- [X] T034 [US5] Wire the separate `_render_stale_banner` callback in `src/pages/risk.py`:
  `Input("risk-var-store", "data")` → renders the banner `html.Div` into
  `risk-var-stale-banner.children` when `status.missing_dates > 0`, else an empty `html.Div`, per
  ui-contract.md #4. Confirm T032 passes.
- [X] T035 [US5] Run the US5 BDD scenarios; confirm green.

**Checkpoint**: The view's two failure-adjacent states are explicit and tested, not left to
whatever a blank chart happens to render.

---

## Phase 8: User Story 6 - Focus on Reliable Observations Only (Priority: P3)

**Goal**: The "hide degraded-quality dates" toggle removes those dates from the chart and swaps
the backtest panel to the matching pre-fetched result.

**Independent Test**: With a range containing a degraded date, toggle hide-degraded on; that
date's bar/overlay point disappears and the panel's figures change; toggle off; both revert.

### Tests for User Story 6 (write first, must fail)

- [X] T036 [P] [US6] Extend `tests/unit/test_var_chart.py` and `tests/unit/test_var_backtest_panel.py`
  with failing cases: `build_figures(..., hide_degraded=True)` omits `degraded`-quality entries'
  bars and overlay points that `hide_degraded=False` includes; `build_panel(..., hide_degraded=True)`
  selects the `min_quality="ok"` result instead of `"degraded"`. Run and confirm they fail.
- [X] T037 [P] [US6] Write failing BDD scenarios in a new
  `tests/bdd/features/var_risk_hide_degraded.feature` for spec.md US6's two acceptance scenarios.
  Run and confirm they fail.

### Implementation for User Story 6

- [X] T038 [US6] Fix/confirm `_var_chart.build_figures()` (T015) and `_var_backtest_panel.build_panel()`
  (T020) satisfy T036 — both parameters were anticipated in their T013/T018 signatures, so this
  task is most likely a verification pass, with a small fix only if one was missed. Confirm T036
  passes.
- [X] T039 [US6] Run the US6 BDD scenarios; confirm green.

**Checkpoint**: All six user stories are independently demoable; the view is feature-complete per
spec.md.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T040 Follow every step of `quickstart.md` manually against a running
  `portfolio-analysis-service` (with at least one account's VaR calculation completed) and the
  Dash dev server; confirm each expected behaviour, including the Network-tab check that instant
  controls make zero new requests.
- [X] T041 Run `ruff check .` and `mypy .` from `portfolio-browser/`; fix any finding. Run the full
  `python -m pytest` suite; fix any failure (including any pre-existing histogram-tab BDD scenario
  that asserted on the page's old, non-tabbed DOM structure and now needs updating for the new
  `dbc.Tabs` wrapper, per plan.md's Risks).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS every user story (models, client methods,
  tab shell, controls, both fetch callbacks are all shared prerequisites).
- **US1, US2 (Phase 3, 4)**: Both P1, both depend only on Foundational. US2 depends on US1 having
  introduced the `_render_var_view` callback (T016) to extend, so US2 cannot start implementation
  before T016 lands, even though its own tests (T018/T019) can be written in parallel with US1's.
- **US3, US4 (Phase 5, 6)**: Both P2, both depend on US1+US2's callback existing (they audit/extend
  its wiring) — cannot start before T021.
- **US5 (Phase 7)**: P2, depends on US1+US2's callback (extends its branching) — cannot start
  before T021.
- **US6 (Phase 8)**: P3, depends on US1+US2's builders (`_var_chart.py`, `_var_backtest_panel.py`)
  already accepting the `hide_degraded` parameter — cannot start before T020.
- **Polish (Phase 9)**: Depends on all six user stories.

### Within Each User Story

- Tests MUST be written and seen to fail before implementation starts.
- Pure builder modules (`_var_chart.py`, `_var_backtest_panel.py`) before the callback that calls
  them.

### Parallel Opportunities

- Within Foundational: T001 (models test) and T003 (client test) and T005 (controls test) touch
  different files and can be written in parallel; their implementation tasks (T002/T004/T006)
  must wait for their own test task but not each other's.
- US1's T013 (chart unit test) and T014 (BDD) can be written in parallel with US2's T018/T019
  (different files), even though US2's *implementation* must wait for US1's T016.
- US3/US4/US5's test-writing tasks (T023, T028, T031+T032) can all be written in parallel with
  each other — they touch disjoint new files — though all three stories' implementation tasks
  wait on T021.

---

## Parallel Example: Foundational

```bash
Task: "Write failing model tests in tests/unit/test_portfolio_analysis_models.py (T001)"
Task: "Write failing client tests in tests/unit/test_portfolio_analysis_client.py (T003)"
Task: "Write failing controls tests in tests/unit/test_var_controls.py (T005)"
```

## Parallel Example: User Story 1 and User Story 2 test-writing

```bash
Task: "Write failing tests/unit/test_var_chart.py (T013)"
Task: "Write failing tests/bdd/features/var_risk_chart.feature (T014)"
Task: "Write failing tests/unit/test_var_backtest_panel.py (T018)"
Task: "Write failing tests/bdd/features/var_risk_backtest_panel.feature (T019)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (nothing) + Phase 2 (Foundational — models, client, tab shell, controls, both
   fetch callbacks).
2. Complete Phase 3 (US1) — the chart renders.
3. **STOP and VALIDATE**: open the tab for a real account with completed VaR data; see bars + VaR
   overlay + exceedance highlighting.
4. This alone is demoable — the panel, instant-toggle proof, refetch proof, empty/stale states and
   degraded-hiding are all refinements of a now-visible picture.

### Incremental Delivery

1. Foundational → nothing visible yet beyond an extra, empty tab.
2. US1 → chart renders (MVP).
3. US2 → panel renders alongside it (the view's full core value).
4. US3 → proves the instant controls are actually network-free.
5. US4 → proves refetch-on-navigation parity with every other page.
6. US5 → proves the two failure-adjacent states are handled explicitly.
7. US6 → the degraded-date refinement.
8. Polish → quickstart + full quality gate.
