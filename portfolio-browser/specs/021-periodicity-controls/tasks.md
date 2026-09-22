---

description: "Task list for Periodicity Control for Overview & Positions"
---

# Tasks: Periodicity Control for Overview & Positions

**Input**: Design documents from `specs/021-periodicity-controls/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/portfolio-analysis-api.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's Principle III
("Test-First with BDD") is non-negotiable. Each test task states what it must fail on before its
implementation exists.

**Organization**: Tasks are grouped by user story (P1–P3, from spec.md). Each phase leaves the app
in a working state:

- **Foundational** adds the config, the shared builder, the client parameter and the model field —
  none of it wired to a page, so nothing changes for a user yet.
- **US1/US2** wire the control into Overview then Positions with a static `day` default, so each
  page behaves exactly as it does today until the user clicks a button.
- **US3** replaces that static default with the duration-derived rule.

That ordering is deliberate: it means `derive_periodicity()` belongs to US3 rather than
Foundational, and US1 is shippable without it.

**⚠️ Deviation from plan.md's file layout**: plan.md proposed a single
`tests/bdd/features/periodicity_control.feature` plus a new steps module. The codebase's actual
convention is **one feature file per page/topic**, registered via `scenarios(...)` inside that
page's existing steps module (`tests/bdd/steps/test_overview_steps.py`,
`test_positions_steps.py`), each of which already owns a `_FakeClient`. These tasks follow the
codebase convention instead — two feature files, no new steps module — because the fakes the
scenarios need already live in those modules.

**⚠️ Deployment prerequisite**: the `portfolio-analysis-service` process must be running its
**feature-008** code. The instance checked during planning predates it and silently ignores
`periodicity` (see contracts/portfolio-analysis-api.md). Unit and BDD tests use fakes and are
unaffected; **T031's quickstart pass requires a restarted service.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US3)
- All file paths are relative to `portfolio-browser/`

---

## Phase 1: Setup

**Purpose**: Project initialization and configuration scaffolding.

**No tasks required.** No new runtime dependency (`dash`, `dash-bootstrap-components`, `plotly`,
`pydantic`, `pyyaml`, `httpx` are all already declared in `pyproject.toml`), no new pytest marker
(this project registers none — BDD features are bound by `scenarios(...)` calls), and no new
`.env` setting. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The configuration vocabulary, the shared control builder, the outbound query
parameter and the response field — everything US1 and US2 both need, with nothing yet wired to a
page.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (write first — all three MUST FAIL)

- [X] T001 [P] Add config-validation tests to `tests/unit/test_content_config.py`: a valid
  `periodicity:` section loads with five options in declared order, `label == "Periodicity"`, and
  the `year` option carrying `value == "annual"`; and `ValueError` is raised for each invalid
  shape — four options, six options, duplicate `key`, duplicate `label`, duplicate `value`,
  non-ascending thresholds (`month_max_years <= day_max_years`), a zero/negative threshold, and a
  threshold whose target interval is missing from `options`. MUST FAIL: `ContentConfig` has no
  `periodicity` field

- [X] T002 [P] Create `tests/unit/test_periodicity_controls.py` covering
  `build_periodicity_control()`: it returns a label whose text comes from config plus exactly five
  buttons in config order; every component id is prefixed with the supplied `page_prefix` (assert
  both `overview-parameters-periodicity-month` and `positions-parameters-periodicity-month` are
  produced from the same call with different prefixes, and that **no** id starts with
  `app-parameters-`); and the active-state helper marks exactly the matching button
  `active=True, outline=False` with the other four inverted. MUST FAIL:
  `src/components/periodicity_controls.py` does not exist

- [X] T003 [P] Add client tests to `tests/unit/test_portfolio_analysis_client.py`: `get_timeseries`
  and `get_position_timeseries` each send `periodicity=<value>` in the query string when the
  argument is supplied, **omit the parameter entirely** when it is `None` or not passed (the
  backward-compatibility guarantee), and parse a response whose body carries a `periodicity`
  field; plus a response **without** that field still validates (pre-008 service) and triggers a
  logged warning rather than an exception. MUST FAIL: the methods take no `periodicity` argument

### Implementation for Foundational

- [X] T004 [P] Add the `periodicity:` section to `config/content.yaml` exactly as specified in
  contracts/ui-contract.md §3 — `label: "Periodicity"`, the five `{key, label, value}` options in
  order (`year` → `annual`), and `thresholds: {day_max_years: 1, month_max_years: 3,
  quarter_max_years: 5}`

- [X] T005 Add `PeriodicityOption`, `PeriodicityThresholds` and `PeriodicityConfig` models to
  `config/content.py` per data-model.md §1–2, hang `periodicity: PeriodicityConfig` off
  `ContentConfig`, and implement the model validators enforcing every rule T001 asserts. Follow
  the existing `nav_sections` validator style (fail fast with a descriptive `ValueError`).
  Depends on T004; makes T001 pass

- [X] T006 [P] Add `periodicity: str | None = None` to `TimeSeriesResponse` and
  `PositionTimeSeriesResponse` in `src/models/portfolio_analysis.py` (data-model.md §5). Optional
  with a `None` default so a pre-008 response still validates

- [X] T007 Create `src/components/periodicity_controls.py` with the option-key constants
  (`PERIODICITY_DAY`…`PERIODICITY_YEAR`, documented as a fixed spec-defined set mirroring
  `date_range_controls.py`'s shortcut codes), `periodicity_component_id(page_prefix, key)`,
  `build_periodicity_control(page_prefix, config)` returning the label + `dbc.ButtonGroup` as
  `dbc.Col`s ready to splice into a `dbc.Row`, and the active-state helper. No I/O, no Dash
  callbacks, full annotations and Google-style docstrings. Depends on T005; makes T002 pass

- [X] T008 Add `periodicity: str | None = None` to `get_timeseries()` and
  `get_position_timeseries()` on **both** the `PortfolioAnalysisClient` Protocol and
  `HttpPortfolioAnalysisClient` in `src/services/portfolio_analysis_client.py`, appending
  `("periodicity", periodicity)` to the existing params list **only when not None**; and after
  parsing, log a `structlog` warning when the response's echoed `periodicity` is absent or differs
  from what was requested (research.md §6 — this is the guard against a pre-008 service silently
  ignoring the parameter). Depends on T006; makes T003 pass

- [X] T009 Run `pytest tests/unit/test_content_config.py tests/unit/test_periodicity_controls.py tests/unit/test_portfolio_analysis_client.py -q`
  and confirm all pass; run `ruff check .` and `mypy config src app.py` and resolve every issue.
  Depends on T005, T007, T008

**Checkpoint**: Config, builder, client parameter and model field all exist and are unit-tested.
No page renders the control yet, so the full existing suite must still pass unchanged.

---

## Phase 3: User Story 1 - Choose How Densely a Chart Is Plotted (Priority: P1) 🎯 MVP

**Goal**: The Overview page shows the Periodicity control, and clicking an interval redraws the
chart at that interval while leaving every other selection untouched.

**Independent Test**: Open Overview for an account with several years of history, set a multi-year
range, click "year", and verify the chart redraws with one point per calendar year with account,
dates and metrics unchanged; click "day" and verify it returns to the per-business-day chart.

### Tests for User Story 1 (write first — MUST FAIL)

- [X] T010 [P] [US1] Create `tests/bdd/features/overview_periodicity.feature` with the four US1
  scenarios from spec.md (control present with the five options in order; selecting "year" redraws
  at one point per year with other selections unchanged; each of week/month/quarter/year maps to
  the matching aggregation; selecting "day" reproduces the pre-existing chart)

- [X] T011 [P] [US1] Register that feature in `tests/bdd/steps/test_overview_steps.py` via
  `scenarios("../features/overview_periodicity.feature")` and add its step definitions. Extend
  that module's existing `_FakeClient` to **record the `periodicity` argument it receives** and to
  return entries aggregated to the requested interval, so a scenario can assert both what was
  requested and what was plotted. MUST FAIL: the Overview parameters bar has no periodicity
  control, so the "control is present" step cannot find it

### Implementation for User Story 1

- [X] T012 [US1] Add `dcc.Store(id="overview-periodicity-store", data={"value": <day option's
  value>, "explicit": False})` to `src/pages/overview.py`'s page layout, beside the existing
  `overview-accounts-store`. The static `day` default is deliberate and temporary — it keeps the
  page behaving exactly as it does today until US3 adds derivation. Read the value from the loaded
  content config rather than hard-coding `"day"` (Principle IV)

- [X] T013 [US1] Add `_apply_periodicity_click` to `src/pages/overview.py`: Inputs are the five
  `overview-parameters-periodicity-{key}` buttons' `n_clicks` plus the page-local
  `overview-mount-trigger.max_intervals` scoping Input; Output is the store's `data`. Use
  `ctx.triggered_id` to map the clicked id back to its option and write
  `{"value": <option value>, "explicit": True}`; `PreventUpdate` when no button was actually
  clicked (guards the mount-time fire). Depends on T007, T012

- [X] T014 [US1] Add `_style_periodicity_buttons` to `src/pages/overview.py`: Input is the store's
  `data`; Outputs are each button's `active` and `outline` props, set from the shared active-state
  helper so exactly one button is highlighted (FR-011). Depends on T007, T012

- [X] T015 [US1] Extend `_render_chart` in `src/pages/overview.py`: add the store as an Input,
  `PreventUpdate` while it is empty, and pass `periodicity=store["value"]` to
  `client.get_timeseries(...)`. Add the five periodicity button ids to the callback's existing
  `running=[...]` disabled-during-refresh list (FR-016). Change nothing else about the callback.
  Depends on T008, T012

- [X] T016 [US1] Splice the control into `_build_overview_parameters_bar()` in
  `src/layout/shell.py` — `[*build_account_date_controls(), *build_periodicity_control("overview", config)]`
  — after the shortcut button group. Thread the content config through to the builder in whatever
  way `shell.py` already has it available (`build_shell` receives a `ContentConfig`). Do **not**
  touch `_build_performance_parameters_bar` or `_build_static_parameters_bar` (FR-007).
  Depends on T007

- [X] T017 [US1] Run the US1 scenarios and confirm all four pass; then run the pre-existing
  `overview_*.feature` suites (default chart, switch account, date range, shortcuts, metric
  toggles, pie chart, winners/losers, empty/error states) plus
  `shell_parameters_bar_unchanged.feature` and confirm zero regressions. Depends on T016

**Checkpoint**: Overview has a fully working Periodicity control. Positions and Performance are
untouched.

### T017 Verification Record (2026-09-22)

**Method**: Chrome is not installed on this machine, so `pytest tests/bdd --headless`
(pytest-bdd + Selenium) could not execute -- the same constraint that hid feature 020's callback
collision. Following that feature's precedent, the Overview page's real callback graph was
replayed over its live `POST /_dash-update-component` HTTP endpoint (the same entry point a
browser uses) against **two freshly started, genuinely 008-capable instances**:
`portfolio-analysis-service` (port 8010) and `portfolio-browser` (port 8060,
`PORTFOLIO_ANALYSIS_SERVICE_URL` pointed at 8010) -- verified beforehand to actually run current
008 code (`?periodicity=fortnight` -> 422; real `HL-ISA`/`HL-SIPP` data, not a fake). This is a
**stronger** check than Selenium would give for the aggregation math specifically: it exercises
the real server-side 008 aggregation end to end, not a hand-written BDD fixture's approximation
of it.

**Result: 41/41 checks pass.**

- **US1 Scenario 1** (control present, five options in order) -- verified from
  `app-parameters-bar.children` alone, no account needed: label text "Periodicity", five buttons
  reading exactly `day, week, month, quarter, year`.
- **US1 remaining scenarios** -- for `HL-ISA` over `2018-07-12..2025-12-31`, clicking each of the
  five buttons was confirmed to: set the store to the correct service-side value (`year` ->
  `annual`); latch `explicit: true`; highlight exactly that one button
  (`active`/`outline` correctly inverted on all five); leave the date range untouched; and
  produce a chart whose point count is **exactly equal** to the real service's own returned entry
  count at that interval -- 1950 daily / 391 weekly / 90 monthly / 30 quarterly / 8 annual,
  cross-checked against the live service's own response for the same request.
- **Regression check** -- Positions' and Performance's parameter bars were fetched and confirmed
  to contain **zero** `overview-parameters-periodicity-*` buttons (US2 not yet wired, so nothing
  should have leaked there).
- **Pre-existing behaviour re-verified live** (`t017_regression.py`, 8 checks): account switch
  resets the date range to the newly-selected account's own earliest date; the `YtD` shortcut
  still sets `from` to 1 January; deselecting every metric still shows the empty-state prompt;
  two metrics toggled on still render as two distinct traces; the position pie chart and
  winners/losers table (019) still render. All pass -- the `_render_chart` signature change (new
  `periodicity_data` Input, reordered parameters) and the expanded `running=` disabled-list did
  not disturb any of this.

**Not covered by this method**: DOM/CSS rendering, exact pixel layout, and the literal Selenium
scenario text in `overview_periodicity.feature` were not executed -- only the underlying callback
behaviour they describe. **Recommend one pass of `pytest tests/bdd --headless` on a machine with
Chrome** before considering this feature fully signed off (tracked as T034).

**Cleanup**: both temporary instances (ports 8010, 8060) were stopped after verification. Two
long-running instances from earlier in this session (ports 8000/8050) were found already stopped
when checked afterward -- not stopped by this verification work, and outside this feature's scope
to restart.

---

## Phase 4: User Story 2 - The Same Control on Positions (Priority: P2)

**Goal**: The Positions page offers an identical control that behaves identically, including in
stacked-area mode, applied per position.

**Independent Test**: Open Positions for an account with two or more positions and a multi-year
range, click "quarter", and verify every position's series is plotted at one point per calendar
quarter with the position filter and attribute toggles unaffected; repeat with the stacked area
graph enabled.

### Tests for User Story 2 (write first — MUST FAIL)

- [X] T018 [P] [US2] Create `tests/bdd/features/positions_periodicity.feature` with the four US2
  scenarios from spec.md (identical control with the same five options in the same order;
  selecting "quarter" aggregates every plotted position; periodicity and the stacked-area view
  work together; navigating from Overview leaves Positions' own control in a valid state)

- [X] T019 [P] [US2] Register that feature in `tests/bdd/steps/test_positions_steps.py` via
  `scenarios(...)` and add its step definitions, extending that module's `_FakeClient` to record
  the `periodicity` argument and return per-position aggregated entries **sharing identical window
  dates across positions** (the guarantee stacked mode depends on — contracts/portfolio-analysis-api.md).
  MUST FAIL: the Positions parameters bar has no periodicity control

### Implementation for User Story 2

- [X] T020 [US2] Add `dcc.Store(id="positions-periodicity-store", …)` plus
  `_apply_periodicity_click` and `_style_periodicity_buttons` to `src/pages/positions.py`, using
  the `positions-` id prefix and `positions-mount-trigger.max_intervals` as the page-local scoping
  Input. Same shape as T012–T014; **distinct component ids**, so no callback-id collision with
  Overview's is possible (contracts/ui-contract.md §1). Depends on T007

- [X] T021 [US2] Extend the chart-render callback in `src/pages/positions.py`: add the store as an
  Input, `PreventUpdate` while empty, pass `periodicity=store["value"]` to
  `client.get_position_timeseries(...)`, and add the five periodicity button ids to its
  `running=[...]` list. Verify the stacked/standard mode branch needs no change (it passes entries
  straight to `_build_figure`). Depends on T008, T020

- [X] T022 [US2] Splice the control into `_build_positions_parameters_bar()` in
  `src/layout/shell.py`, after the existing Positions-only controls. Confirm the row wraps rather
  than clips at tablet width — this is the widest bar in the app (research.md §1). Depends on T007

- [X] T023 [US2] Run the US2 scenarios and confirm all four pass; then run the pre-existing
  `positions_*.feature` suites (default view, account/date controls, attribute and position
  filters, comparison table, stacked-area toggle) and confirm zero regressions. Depends on T022

**Checkpoint**: Both pages offer the control with identical behaviour and independent callbacks.

### T023 Verification Record (2026-09-22)

**Method**: same live-service HTTP-replay technique as T017 (Chrome unavailable). Fresh
`portfolio-analysis-service` (port 8010, current 008 code, re-verified: `?periodicity=fortnight`
-> 422) and fresh `portfolio-browser` (port 8060) instances; Positions' real callback graph
driven over `POST /_dash-update-component`, using `HL-ISA`'s real position ladder (`Cash` and
`Barclays plc Ordinary 25p`, both continuous 2018-07-12 through today).

**Result: 51/51 checks pass** (`t023_verify.py`, 46 checks + `t023_regression.py`, 3 checks;
2 informational "n/a" lines).

- **Scenario 1** (identical control) -- Positions' bar carries its own
  `positions-parameters-periodicity-*` ids (confirmed disjoint from Overview's), same five
  labels in the same order.
- **Scenario 2** (aggregates every position) -- for `2019-01-01..2025-12-31`, each of the five
  intervals was confirmed to set the correct store value, latch `explicit`, highlight exactly one
  button, and -- independently for **both** `Cash` and `Barclays plc Ordinary 25p` -- produce a
  trace whose point count exactly matches the real service's own per-position entry count:
  1827 daily / 366 weekly / 84 monthly / 28 quarterly / 7 annual (both positions identical, as
  expected for a shared date range). Positions selected, attributes toggled and the date range
  were confirmed unchanged after every click.
- **Cross-position window-date alignment** -- at every interval other than `day`, both positions'
  traces were confirmed to share **identical** x-axis (window) dates -- the 008 guarantee that
  stacked-area mode depends on, checked directly rather than assumed.
- **Scenario 3** (stacked-area + periodicity) -- with the stacked toggle on and `periodicity=month`,
  the rendered chart's two traces both carry `stackgroup: "positions"` and both show exactly the
  84 monthly points the real service returns for that position -- confirming FR-014 end to end
  against real aggregation, not a fixture.
- **Regression** -- switching to `HL-SIPP` still resets the date range to YtD (not Overview's
  full-history default -- 018's own per-page distinction is intact); the position filter still
  resets to the new account's positions; deselecting every attribute or every position still
  shows `positions-empty-state`; the stacked-area toggle still auto-disables once a second
  attribute is selected. All match pre-021 behaviour.

**Not covered by this method**: DOM/CSS rendering and the literal Selenium scenario text in
`positions_periodicity.feature` (Scenario 4, the cross-page store-isolation check, was not
exercised by this HTTP-replay method since it depends on client-side page routing state that the
callback-replay technique doesn't model). **Recommend `pytest tests/bdd --headless` on a machine
with Chrome** (tracked as T034) to close that gap and formally execute all Gherkin text.

**Cleanup**: both temporary instances (ports 8010, 8060) were stopped after verification.

---

## Phase 5: User Story 3 - Long Ranges Are Legible Without Touching the Control (Priority: P3)

**Goal**: With no explicit choice made, the interval follows the date-range span (≤1y → day,
≤3y → month, ≤5y → quarter, longer → year); once the user clicks, their choice sticks.

**Independent Test**: With no click, set ranges of six months, two years, four years and ten years
in turn and verify the chart is plotted at day, month, quarter and year respectively; then click
"month", click "All", and verify it stays monthly.

### Tests for User Story 3 (write first — MUST FAIL)

- [X] T024 [P] [US3] Create `tests/unit/test_periodicity_derivation.py` covering
  `derive_periodicity(from_date, to_date, thresholds)`: the four bands (6 months → day, 2 years →
  month, 4 years → quarter, 10 years → year); **both sides of every boundary** — exactly 1/3/5
  years resolve to the finer interval (day/month/quarter) while one day beyond each resolves to
  the coarser one; `week` is never returned for any span from one day to twenty years; degenerate
  inputs return `day` without raising (`from == to`, and an inverted `from > to`); and that the
  thresholds come from the passed config rather than constants (pass a non-default config and
  assert the bands move). MUST FAIL: `derive_periodicity` does not exist

- [X] T025 [P] [US3] Append the US3 scenarios from spec.md to
  `tests/bdd/features/overview_periodicity.feature` (the span→interval Scenario Outline, the "5Y"
  shortcut deriving quarter, the account switch deriving year, "week" never auto-selected, an
  explicit choice surviving a later range change, and an explicit choice surviving an account
  switch) and add the corresponding steps to `tests/bdd/steps/test_overview_steps.py`. MUST FAIL:
  the interval is currently a static `day` default and never derived

### Implementation for User Story 3

- [X] T026 [US3] Add `derive_periodicity(from_date, to_date, thresholds) -> str` to
  `src/components/periodicity_controls.py` per data-model.md §4: inclusive comparisons against
  `date_range_controls._years_before(to_date, n)` so the boundary resolves to the finer interval
  and the arithmetic matches the 1Y/3Y/5Y shortcut buttons exactly (leap-day fallback included);
  returns `day` for degenerate/inverted input; pure, no clock read. Reuse the existing helper —
  do not copy or re-derive it. Depends on T007; makes T024 pass

- [X] T027 [US3] Add `_derive_periodicity_from_range` to `src/pages/overview.py`: Inputs are
  `app-parameters-from-date.date`, `app-parameters-to-date.date` and the page-local scoping Input;
  State is the store's `data`; Output is the store's `data` with `allow_duplicate=True`.
  `PreventUpdate` when either date is missing **or** when `store["explicit"]` is true (FR-012);
  otherwise write `{"value": <derived option's value>, "explicit": False}`. This callback must
  never set `explicit`. Then change T012's store initialiser to an empty/None `data` so the
  derived value — not a static `day` — is what first populates it. Depends on T026

- [X] T028 [US3] Add the identical `_derive_periodicity_from_range` to `src/pages/positions.py`
  with the `positions-` ids and its own scoping Input, and make the same store-initialiser change.
  Note Positions' own default range is "YtD" (018 research #1a), so its derived interval on first
  load is normally `day` — that is correct, not a bug. Depends on T026

- [X] T029 [US3] Run T024 and the US3 scenarios and confirm all pass; add the two
  explicit-choice-survives scenarios to `tests/bdd/features/positions_periodicity.feature` and its
  steps so the sticky rule is covered on both pages (FR-006); re-run both pages' full BDD suites
  and confirm zero regressions. Depends on T027, T028

**Checkpoint**: All three user stories complete on both pages.

### T029 Verification Record (2026-09-22)

**Note on T026**: `derive_periodicity()` was written as part of T007 (the shared component
module), ahead of its own designated task -- it made sense to write the builder and the
derivation function together. T024's dedicated unit tests therefore did not observe a true
red-green cycle (the implementation already existed); they passed immediately, all 24 of them.
Flagged here rather than silently claiming a red-green cycle that did not happen.

**Deviation from the task text**: T029 asks for the two sticky-choice scenarios to be added to
`positions_periodicity.feature`; they were not present after T018/T019 (US2) and have now been
added here, along with a second account fixture (`PERIODICITY-POSITIONS-2`) and its Given step,
so Positions carries the same FR-006 stickiness coverage Overview does.

**Method**: same live-service HTTP-replay technique as T017/T023. Fresh `portfolio-analysis-service`
(port 8010) and `portfolio-browser` (port 8060) instances; real `HL-ISA`/`HL-SIPP` data. The
expected derived interval was computed by **calling the real production `derive_periodicity()`
function directly** (imported from `src.components.periodicity_controls`), not re-implemented in
the verification script -- so this checks the wiring around the function, not a second copy of
its logic.

**Result: 15/15 checks pass** across three scripts.

- **Overview** (`t029_verify.py`, 8 checks) -- for `HL-ISA`'s real full-history default range
  (`2018-07-12..2026-09-21`, ~8 years), the live store derived `annual`, matching
  `derive_periodicity()` called directly on the same dates. Confirmed the derived value never
  latches `explicit`, and is never `week`. Then: an explicit click to `month` latches
  `explicit=True`; clicking the `1Y` shortcut afterward genuinely narrows the date range
  (`2018-07-12` -> `2025-09-22`); and the derive callback, invoked with the new dates and the
  still-`explicit` store as State, returns **HTTP 204** (Dash's PreventUpdate response) -- the
  store is untouched, exactly as FR-012 requires.
- **Positions** (`t029_positions_verify.py`, 2 checks) -- Positions' own YtD default
  (`2026-01-01..2026-09-21`, under a year) correctly derives `day`, matching
  `derive_periodicity()` directly -- confirmed independent of, and different from, Overview's
  full-history default for the same real account.
- **Positions stickiness** (`t029_positions_sticky.py`, 4 checks) -- an explicit click to
  `quarter` latches; switching from `HL-ISA` to `HL-SIPP` produces a newly-resolved YtD range for
  the new account; the derive callback, invoked with the new dates and the still-`explicit`
  store, again returns 204 -- the store stays `quarter` across the account switch. One assumption
  in the harness's first draft was wrong and corrected: Positions always resets to YtD regardless
  of account, so the resolved *dates* can coincide across a genuine account switch (both real
  accounts are >1 year old) -- the assertion was changed to check the switch itself rather than
  assume the dates must differ.

**Not covered by this method**: the literal Gherkin text in `overview_periodicity_defaults.feature`
and the two new `positions_periodicity.feature` scenarios were not executed as Selenium scenarios
-- only the callback behaviour they describe, via direct comparison against the real
`derive_periodicity()` function. **Recommend `pytest tests/bdd --headless` on a machine with
Chrome** (T034) to formally execute all Gherkin text end to end.

**Cleanup**: all temporary instances (ports 8010, 8060, across three verification passes) were
stopped after each check.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, registry safety, and end-to-end validation against a real service.

- [X] T030 [P] Run `ruff check .` and `ruff format` on every new and changed file
  (`config/content.py`, `config/content.yaml`, `src/components/periodicity_controls.py`,
  `src/layout/shell.py`, `src/pages/overview.py`, `src/pages/positions.py`,
  `src/services/portfolio_analysis_client.py`, `src/models/portfolio_analysis.py`, and all new/
  changed test files); run `mypy config src app.py` and resolve every error; confirm all clean

- [X] T031 [P] Run `pytest tests/unit/test_callback_registration.py -v` and confirm it still
  reports **zero** overwritten registrations. This is the guard that the new per-page callbacks did
  not collide — if it fails, two pages have been given the same Output+Input pair and the
  per-page-id decision in contracts/ui-contract.md §1 has been undone

- [X] T032 Run `pytest tests/unit -q` and confirm zero failures across the whole unit suite
  (104 pre-existing + the registry guard + this feature's new tests)

- [X] T033 Run `specs/021-periodicity-controls/quickstart.md` end to end against a
  **restarted** `portfolio-analysis-service` carrying its feature-008 code. Start with the
  quickstart's step 0 service check (`?periodicity=annual` must echo `"periodicity":"annual"` and
  return ~10 entries for a ten-year range; `?periodicity=fortnight` must return 422) — if that
  check fails, the service is the pre-008 build and the rest of the walkthrough is invalid. Then
  confirm each documented behaviour: the control on both pages, the derived-interval table across
  all five shortcuts, the sticky-choice behaviour, `year` sending `annual` on the wire, and the
  stacked-area view at a coarse interval. Record any discrepancy in `quickstart.md`.
  Depends on T029

### T033 Verification Record (2026-09-22)

**Method**: fresh instances on the quickstart's own documented ports (`portfolio-analysis-service`
:8000, `portfolio-browser` :8050), driven the same way as T017/T023/T029. Section 0's service
check was run exactly as documented first (both the `periodicity=annual` echo/count check and the
`periodicity=fortnight` 422 check passed on the first try -- no discrepancy). Sections 1-3 were
then replayed against the live callback graph.

**Result: 9/9 checks pass**, plus section 4's exact curl example re-run verbatim (`annual 10` --
byte-for-byte what the doc claims).

- **Section 1**: the Periodicity label and all five buttons (day/week/month/quarter/year)
  confirmed present in that order.
- **Section 2**: the default account's (HL-ISA, real data) full-history range derives `annual`
  with no click, matching "about ten points... without you having clicked anything". The full
  shortcut table was reproduced exactly: YtD->day, 1Y->day, 3Y->month, 5Y->quarter, All->annual.
- **Section 3**: clicking `month` then `All` leaves the store untouched (still `month`) -- the
  derive callback returns HTTP 204 (PreventUpdate) for the same reason verified in T029.
- **Section 4**: `curl` example re-run verbatim, output exactly `annual 10` as documented.
- **Section 5**: already covered in depth by T023 (stacked mode + cross-position window-date
  alignment against real data) -- not re-run here to avoid duplicating that verification.

**One discrepancy found and fixed**: section 6 referenced a single `tests/bdd/features/
periodicity_control.feature`, which was never the actual filename (plan.md's original proposal,
superseded by the file-per-page convention noted in this document's own header). Corrected to
name the three real files: `overview_periodicity.feature`, `overview_periodicity_defaults
.feature`, `positions_periodicity.feature`.

**Cleanup**: both temporary instances (ports 8000, 8050) were stopped after verification.

- [X] T034 Run `pytest tests/bdd --headless` **on a machine with Chrome installed** and confirm
  every scenario passes. `dash[testing]` drives a real browser via Selenium, so this cannot run on
  a machine without Chrome — the environment used for this feature's development has none, which
  is the same gap that hid feature 020's callback collision. This task is environment-gated, not
  optional: the constitution's Principle III requires the scenarios to be executable, so they must
  be executed somewhere before the feature is considered done. Depends on T029

  **Closed by decision, not by execution (2026-09-22)**: the user asked that no test in this
  project depend on Chrome to report a pass, since this and (per audit) every other development
  environment used so far for this repository lacks it. Rather than continue leaving this open
  indefinitely across every feature that touches `tests/bdd/`, `tests/bdd/conftest.py` now
  applies an environment-conditional `pytest.mark.skip` to every BDD item (both browser binary
  and chromedriver are probed; missing either skips) -- see that file's own docstring for the
  full rationale. This directly satisfies "remove them or mark them as disabled" as stated,
  while keeping Principle III's letter intact: the scenarios are not deleted, nothing about them
  is hardcoded to fail, and they resume running for real automatically wherever Chrome +
  chromedriver are both present. Verified: `pytest tests/bdd` -> 115 skipped, 0 failed, ~0.3s;
  bare `pytest` -> 163 passed, 115 skipped, exit 0, ~5s (previously this would hang indefinitely
  on the first `dash_duo` fixture). The equivalent open tasks in specs/015, /016 and /017 (T019,
  T026, T029, T027, T014) were closed the same way, for the same reason, at the same time --
  this was a suite-wide fix, not specific to 021.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no tasks
- **Foundational (Phase 2)**: T001–T009 — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: depends on Phase 2 only
- **User Story 2 (Phase 4)**: depends on Phase 2 only — **not** on User Story 1
- **User Story 3 (Phase 5)**: depends on Phase 2, and on at least one of US1/US2 having wired a
  store for the derive callback to write into (T027 needs T012; T028 needs T020)
- **Polish (Phase 6)**: depends on all desired story phases

### Critical Path

```text
T004 (config.yaml) -> T005 (config models) -> T007 (builder) ─┬─> T012..T016 (US1 wiring)
                                                              ├─> T020..T022 (US2 wiring)
                                                              └─> T026 (derive) ─┬─> T027 (US1)
T006 (models) -> T008 (client param) ─────────────────────────────────────────────┴─> T028 (US2)
                                                                       all ──> T032 ──> T033/T034
```

`T004 → T005 → T007` is the root chain: nothing can be wired to a page until the builder exists,
and the builder needs the validated config.

### Within Each User Story

- Tests are written and confirmed FAILING before implementation
- Config/models before the component; the component before page wiring; page wiring before the
  shell splice; the splice before verification
- Each story's verification task re-runs the pre-existing suites for the page it touched, so a
  regression is caught inside the story rather than at Phase 6

### Parallel Opportunities

- **Phase 2**: T001 + T002 + T003 together (three different test files); then T004 + T006 together
  (different files); T005/T007/T008 are each single-file and sequential only along the chain above
- **Phase 3 / 4**: each story's feature-file task and steps task are marked [P] (different files).
  **Caution**: T011 and T025 both edit `tests/bdd/steps/test_overview_steps.py`, and T019 and T029
  both edit `test_positions_steps.py` — do not run those pairs concurrently
- **Across stories**: once Phase 2 is complete, US1 (T010–T017) and US2 (T018–T023) touch disjoint
  page files (`overview.py` vs `positions.py`) and disjoint feature/steps files. The only shared
  file is `src/layout/shell.py` (T016 and T022 edit different functions in it), so two people can
  work in parallel with one light coordination point
- **Phase 6**: T030 + T031 in parallel; T032 then T033/T034 last

---

## Parallel Example: Phase 2 Foundational

```bash
# Write all three failing unit-test files together:
Task: "Add config-validation tests to tests/unit/test_content_config.py"
Task: "Create tests/unit/test_periodicity_controls.py for the shared builder"
Task: "Add periodicity client tests to tests/unit/test_portfolio_analysis_client.py"

# Then the two independent data/model edits together:
Task: "Add the periodicity: section to config/content.yaml"
Task: "Add the optional periodicity field to both response models"
```

---

## Implementation Strategy

### MVP First (Foundational + User Story 1)

1. Phase 1: nothing to do
2. Phase 2: T001–T009 — config, builder, client parameter, model field
3. Phase 3: T010–T017 — the Overview control
4. **STOP and VALIDATE**: a multi-year Overview chart can be switched to yearly in one click; the
   page is otherwise unchanged
5. Ship — Overview is the page where the dense-chart problem is felt most

### Incremental Delivery

1. Foundational → nothing user-visible, full suite still green
2. \+ US1 → Overview gains the control, default still `day` (**MVP**)
3. \+ US2 → Positions gains the same control, including stacked mode
4. \+ US3 → long ranges become legible with no interaction, explicit choices stick
5. \+ Polish → gates, registry guard, real-service walkthrough, BDD on a Chrome host

### Parallel Team Strategy

1. Both developers complete Phase 2 together (or one takes T004/T005/T007, the other T006/T008)
2. Then: Developer A takes US1, Developer B takes US2 — disjoint page and test files, coordinating
   only on the two `shell.py` builder functions
3. Either developer takes US3 once their page is wired (T026 is shared; T027/T028 are per-page)
4. Polish together

---

## Notes

- **The two load-bearing guarantees** are FR-011 (the control always shows the interval in effect)
  and FR-012 (an explicit choice is sticky). Both are held by the store design, not by
  discipline: the store is the single source of truth that both the buttons and the chart read,
  and `explicit` is only ever set by a click. T013/T020's `PreventUpdate`-on-no-click guard and
  T027/T028's `PreventUpdate`-on-explicit guard are the two lines that must not be weakened
- **Do not switch to shared component ids.** Per-page ids are what make a 020-style callback
  collision impossible here; T031 is the tripwire
- **Do not add aggregation logic to the UI.** The service decides period boundaries, representative
  values and empty-period omission (Principle I). If a chart looks wrong at a coarse interval, the
  fix is in the analysis service, not here
- `[P]` tasks = different files, no dependencies on incomplete tasks
- Verify each test task FAILS before writing its implementation (Principle III, non-negotiable)
- Commit after each task or logical group
- **Not in scope** (recorded so it is not added opportunistically): a sixth "Auto" option;
  persisting the choice across reloads; bar/column rendering at coarse intervals; a periodicity
  control on the Performance or Income pages; compounded period returns; and any client-side
  re-derivation of returns
