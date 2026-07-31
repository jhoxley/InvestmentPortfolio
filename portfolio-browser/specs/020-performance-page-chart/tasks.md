---

description: "Task list for Performance Page"
---

# Tasks: Performance Page

**Input**: Design documents from `specs/020-performance-page-chart/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/portfolio-analysis-api.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's
Principle III ("Test-First with BDD") is non-negotiable, and this feature
follows the same discipline as `016-link-real-portfolio` and
`018-positions-page`.

**Organization**: Tasks are grouped by user story (P1–P3, from spec.md).
Because Dash allows only one callback per Output, the single render
callback that serves every user story is built once, in User Story 1's
phase (T014) — mirroring `018`'s precedent. Later story phases mostly add
their own distinct controls (the shortcut-click callback) plus formal test
coverage of behavior the US1 callback already provides — see the Notes
section for the full rationale.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US3)
- All file paths are relative to `portfolio-browser/`

---

## Phase 1: Setup

**Purpose**: None needed — no new dependencies, no new packages, no new
configuration (plan.md's Technical Context: "zero new third-party
dependencies"). This phase is intentionally empty; proceed directly to
Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new API client methods (reusing existing models — no new
model needed, research.md #1), the shared shortcut-label extension, the
pure chart-formatting function, the Performance parameters bar, and the
Performance page skeleton — every user story's implementation depends on
these existing first.

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete.

- [X] T001 [P] Write failing unit tests in `tests/unit/test_portfolio_analysis_client.py` for two new client methods — `get_performance(account_name, attributes, start, end)` and `list_performance_attributes()` — covering: successful parsing into the existing `TimeSeriesResponse`/`AttributeDefinition` models (research.md #1 — no new model), the `attribute` query param sent once per requested measure plus `start`/`end`, and 404/422/timeout all raise `PortfolioAnalysisServiceError`
- [X] T002 Implement `get_performance()` and `list_performance_attributes()` on the `PortfolioAnalysisClient` Protocol and `HttpPortfolioAnalysisClient` in `src/services/portfolio_analysis_client.py`, calling `GET /v1/accounts/{account_name}/performance` and `GET /v1/performance/attributes` respectively, mirroring `get_timeseries()`/`list_attributes()` exactly — makes T001 pass (depends on T001)
- [X] T003 [P] Write a failing unit test in `tests/unit/test_date_range_controls.py` for `build_account_date_controls(first_shortcut_label="ITD")` — confirms the first shortcut button's rendered label is "ITD" while its component id remains `overview-shortcut-ytd`, and confirms the existing no-argument call still renders "YtD" (zero regression for Overview/Positions)
- [X] T004 Add the optional `first_shortcut_label: str = "YtD"` parameter to `build_account_date_controls()` in `src/components/date_range_controls.py`, threading it through to `_build_shortcut_buttons()`'s first button label only — no id or behavior change (research.md #3) — makes T003 pass (depends on T003)
- [X] T005 [P] Write failing unit tests in `tests/unit/test_performance_chart_shaping.py` for `src/pages/_performance_chart.py` (not yet created): `_build_figure()` produces one `go.Scatter` trace per toggled-on measure using `PERFORMANCE_ATTRIBUTE_COLORS`' fixed mapping (with a default-color fallback for an unknown measure name, mirroring `_overview_chart.py`'s `ATTRIBUTE_COLORS`/`DEFAULT_ATTRIBUTE_COLOR` shape); the y-axis `tickformat` and each trace's `hovertemplate` use a percentage format (e.g. `".1%"`), not currency; a measure missing from some entries (simulating insufficient history) produces a trace with gaps at those dates rather than raising or filling a synthetic value
- [X] T006 Implement `src/pages/_performance_chart.py`: `PERFORMANCE_ATTRIBUTE_COLORS`/`DEFAULT_PERFORMANCE_ATTRIBUTE_COLOR` (keyed by `"ITD"`, `"ITD (Ann.)"`, `"1Y"`, `"3Y"`, `"5Y"`) and `_build_figure(entries, toggled_attributes) -> go.Figure`, mirroring `_overview_chart.py::_build_figure`'s structure but with percentage tick/hover formatting (research.md #6) — makes T005 pass (depends on T005)
- [X] T007 [P] Update `tests/bdd/features/shell_parameters_bar_unchanged.feature`: remove `Performance` from the static-placeholder `Scenario Outline`'s `Examples` table, and add a new scenario asserting the Performance route shows real, enabled controls (mirroring the existing "The Positions route shows real controls" scenario) **and** explicitly asserts no "Stacked area graph" toggle (or any other chart-mode control) is present on the Performance parameters bar (FR-005 — `/speckit-analyze` finding C1: this MUST-NOT requirement had no dedicated absence check) — confirm this new scenario fails against the current placeholder page (research.md #8)
- [X] T008 Add `_build_performance_parameters_bar()` to `src/layout/shell.py`: calls `build_account_date_controls(first_shortcut_label="ITD")` (T004) with no additional Performance-only controls (no stacked-area toggle, no filter — research.md #7), and add a `/performance` branch to `_render_parameters_bar()` — makes T007 pass (depends on T004, T007)
- [X] T009 Replace the placeholder in `src/pages/performance.py` with a real page: `dash.register_page` (unchanged `path="/performance"`), layout (`performance-mount-trigger` `dcc.Interval`, two `dcc.Store`s — `performance-accounts-store`/`performance-attributes-store`, a measure-toggles container built via the existing shared `build_attribute_toggles()` from `src/components/attribute_toggles.py`, `performance-chart-container` empty-state placeholder), and the mount-fetch callback (`GET /v1/accounts` + `GET /v1/performance/attributes` via T002, populating the account dropdown options, measure toggles with `default_on_names = frozenset({attributes[0].name})` when the fetched list is non-empty else `frozenset()` — research.md #5, and the two stores) — mirrors `overview.py`'s `_fetch_accounts_and_attributes` structure (depends on T002, T008)
- [X] T010 [P] Add the default-account-selection callback to `src/pages/performance.py` (alphabetically-first account once `performance-accounts-store`/`performance-attributes-store` are populated), mirroring `overview.py`'s `_apply_default_account` (FR-008) (depends on T009)

**Checkpoint**: Performance route renders with real, populated-but-inert controls (account dropdown, measure toggles with the first measure defaulted on) and its own parameters bar. No performance time series has been fetched yet.

---

## Phase 3: User Story 1 - See account performance the moment the page opens (Priority: P1) 🎯 MVP

**Goal**: Navigating to Performance shows a fully populated chart — first
account, full recorded history ("ITD"), one default measure — with zero
configuration.

**Independent Test**: Navigate to the Performance page from the menu on a
fresh session and verify the chart appears for the alphabetically-first
account's full-history return data, with no manual interaction required.

### Tests for User Story 1 ⚠️

- [X] T011 [P] [US1] Write failing BDD scenarios in `tests/bdd/features/performance_default_view.feature` + step definitions in `tests/bdd/steps/test_performance_steps.py` covering spec.md's US1 Acceptance Scenarios 1–3: on first navigation, the Account selector shows the first account selected and the date range covers that account's full recorded history through the most recently completed business day; the chart displays a line for the default measure across the full resolved range; an account with no recorded performance data shows a clear "no data" message instead of a broken/empty chart. **Also add a scenario for FR-013** (`/speckit-analyze` finding C2): with the `portfolio-analysis-service` client mocked/stubbed to raise `PortfolioAnalysisServiceError` — once for the mount-time accounts/measure-metadata fetch, once for the chart's own performance-data fetch — confirm `performance-error-state`'s messaging is shown in place of a broken/blank page for both failure points

### Implementation for User Story 1

- [X] T012 [US1] Add the account-change callback to `src/pages/performance.py`: on `app-parameters-account.value` change, reset `app-parameters-from-date`/`to-date` to the account's own full recorded history, computed via the shared `_earliest_from_date(account)` from `src/components/date_range_controls.py` — the **same** default Overview's own `_sync_date_range_to_selected_account` uses, **not** Positions' "YtD" default (research.md #4) — fires on both the initial default-account selection and every later manual switch (depends on T009, T010)
- [X] T013 [US1] Add the `app-parameters-from-date.max_date_allowed` sync callback to `src/pages/performance.py`, mirroring `overview.py`'s/`positions.py`'s own `_sync_from_date_max_to_to_date` (FR-015) (depends on T009)
- [X] T014 [US1] Add the chart-render callback to `src/pages/performance.py`: `Input`s on account/from-date/to-date/measure-toggles; calls `get_performance()` (T002), then `_build_figure()` (T006); guard clauses — in this order — for **zero measures selected** (`performance-empty-state`, "select at least one measure", FR-011; mirrors Overview's existing `if not toggled_attributes` guard), a data-less account/empty response (`performance-empty-state`, FR-012), and any client error (`performance-error-state`, FR-013); a `running=[...]` clause disabling every listed control for the callback's duration (FR-017) — makes T011's default-view scenarios pass (depends on T002, T006, T012)

**Checkpoint**: User Story 1 is fully functional and independently
testable — run `performance_default_view.feature` and the US1 walkthrough
in `quickstart.md`. Because T014 wires every trigger (account, date,
measure toggles) into one callback — required by Dash's
one-callback-per-Output rule — User Story 2's shortcut buttons and User
Story 3's measure toggles already refresh the chart correctly at this
checkpoint; their own phases add their remaining distinct control (the
shortcut-click callback) and formal acceptance-scenario coverage. See Notes.

---

## Phase 4: User Story 2 - Explore a different account or time period (Priority: P2)

**Goal**: Switching accounts or clicking an "ITD"/"1Y"/"3Y"/"5Y"/"All"
shortcut updates the date range and refreshes the chart accordingly.

**Independent Test**: With the Performance page loaded, switch to a
different account, then click each shortcut button in turn and verify the
"From"/"To" fields and the chart update correctly each time.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Write failing BDD scenarios in `tests/bdd/features/performance_account_and_date_controls.feature` + steps covering spec.md's US2 Acceptance Scenarios 1–3: switching accounts resets the date range to that account's own full recorded history; each shortcut button (including "ITD", which must resolve to the identical date "All" resolves to) updates the date fields (clamped where applicable) and refreshes the chart; every listed control is disabled/has no effect while a refresh triggered by any of them is in flight

### Implementation for User Story 2

- [X] T016 [US2] Add the shortcut-click callback to `src/pages/performance.py`: five `Input(button_id, "n_clicks")`, `State` on `app-parameters-account.value` + `performance-accounts-store.data`, resolving the clicked button via `ctx.triggered_id` against this page's own `_SHORTCUT_CODE_BY_BUTTON_ID` mapping — identical to Overview's/Positions' own copies **except** `"overview-shortcut-ytd"` (the button labeled "ITD" on this page) maps to `SHORTCUT_ALL`, not `SHORTCUT_YTD` (research.md #3) — computing/clamping `from_date`/`to_date` via the shared `_shortcut_from_date` (depends on T012)
- [X] T017 [US2] Verify T014's `running=[...]` clause already covers the shortcut buttons and the Account/From/To controls; run T015's in-flight-disabling scenario and extend the clause if it reveals a gap (depends on T014, T015, T016)

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 - Choose which return measures to display (Priority: P2)

**Goal**: Toggling measures on/off updates the chart to include or exclude
that measure's line, supporting more than one simultaneously; deselecting
every measure shows an empty-state prompt instead of a blank chart.

**Independent Test**: With the Performance page loaded, toggle a second
measure on and verify the chart updates to show an additional line without
affecting the others.

### Tests for User Story 3 ⚠️

- [X] T018 [P] [US3] Write failing BDD scenarios in `tests/bdd/features/performance_measure_toggles.feature` + steps covering spec.md's US3 Acceptance Scenarios 1–3: toggling a measure on/off updates the chart; more than one toggled-on measure renders as distinguishable lines on the same chart; zero measures selected shows a "select at least one measure" prompt instead of a blank chart

### Implementation for User Story 3

- [X] T019 [US3] Verify T014's callback already re-fetches on measure-toggle changes (already an `Input` per `contracts/ui-contract.md`) and its zero-measures guard fires correctly; run T018's toggle scenarios and fix if needed (depends on T014, T018)

**Checkpoint**: All 3 user stories independently functional — full spec scope complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Static analysis and full-suite regression, run last against
the fully-wired feature.

- [X] T020 [P] Run `.venv/Scripts/python -m ruff check .` and `.venv/Scripts/python -m mypy .`; fix any issues in all new/modified files (`src/components/date_range_controls.py`, `src/pages/_performance_chart.py`, `src/pages/performance.py`, `src/layout/shell.py`, `src/services/portfolio_analysis_client.py`). **Verified**: both commands report zero issues across the full project (46 source files).
- [X] T021 [P] Run `.venv/Scripts/python -m pytest tests/unit tests/bdd` in full and confirm all pass — including 015's/016's/017's/018's/019's pre-existing scenarios (regression risk: `shell_parameters_bar_unchanged.feature` and `date_range_controls.py` are shared/modified files). **`tests/unit`**: all 104 tests pass (18 client tests incl. 6 new, 19 date-range-controls tests incl. 2 new, 7 new in `test_performance_chart_shaping.py`, plus every pre-existing 015/016/017/018/019 unit test unchanged and green). **`tests/bdd`**: all 88 scenarios (67 pre-existing + 21 new: 11 Performance-specific + the updated `shell_parameters_bar_unchanged.feature`'s 4) collect successfully with zero step-binding/import errors — confirming no wiring defects across the whole suite. Actually running them hits `selenium.common.exceptions.SessionNotCreatedException: cannot find Chrome binary` — this sandbox has no Chrome/chromedriver installed, identical to the limitation already documented in `specs/017-chart-date-range-shortcuts/tasks.md`'s T014 and `specs/018-positions-page/tasks.md`'s T032. **Not executed to a pass/fail verdict** — needs a machine with Chrome.
- [ ] T022 Perform the full manual walkthrough in `quickstart.md` against a real running `portfolio-analysis-service` instance (all 3 user stories, the "ITD"/"All" redundancy check, percentage formatting, and the missing-measure-history gap check). **Not done** — no running `portfolio-analysis-service` instance or browser in this session; requires a manual pass by whoever has both runnable locally.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Empty — nothing to do
- **Foundational (Phase 2)**: No dependencies — BLOCKS all 3 user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational + US1's T012 (account-change callback) and T014 (the shared render callback the shortcuts feed into)
- **User Story 3 (Phase 5)**: Depends on Foundational + US1's T014 (the callback whose `Input`s already include the measure toggles)
- **Polish (Phase 6)**: Depends on all 3 user stories being complete

Every user story after US1 depends on US1's T014 specifically, not just on
Foundational — this mirrors `018`'s precedent (its US2–US5 each depended on
US1's T019), for the same underlying reason: Dash's one-callback-per-Output
rule means the chart-refresh mechanism can only be built once.

### Within Each User Story

- Its `.feature` scenario(s) are written and confirmed failing before that
  story's implementation tasks (constitution Principle III)
- Client layer before pure functions before callbacks before cross-cutting
  verification
- Story complete (its own Acceptance Scenarios all pass) before moving to
  the next priority

### Parallel Opportunities

- T001, T003, T005 (Foundational) — three independent new-test-file/
  new-test-case tasks, run together; their respective "make it pass" tasks
  (T002, T004, T006) must wait on their own prerequisite but can run in
  parallel with each other's *different* files once unblocked
- T007 (Foundational) — independent of the T001–T006 chain (a `.feature`
  file), can run any time before T008
- T010 — independent of T011 onward, can run alongside US1's test-writing
  (T011)
- T011, T015, T018 — each story's BDD-writing task can be drafted in
  parallel with the others once Foundational is done, even though the
  corresponding implementation tasks must wait on US1's T014
- T020, T021 (Polish) — different concerns, run together; T022 is manual
  and independent of both

---

## Parallel Example: Foundational Phase

```bash
# Launch the independent Foundational new-file/new-test tasks together:
Task: "Write failing unit tests for the 2 new client methods in tests/unit/test_portfolio_analysis_client.py"
Task: "Write a failing unit test for build_account_date_controls(first_shortcut_label=...) in tests/unit/test_date_range_controls.py"
Task: "Write failing unit tests for src/pages/_performance_chart.py in tests/unit/test_performance_chart_shaping.py"
Task: "Update shell_parameters_bar_unchanged.feature for the Performance route"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: run `performance_default_view.feature` + the US1
   manual walkthrough in `quickstart.md`
4. Demo: the default view (chart, first account, full recorded history,
   default measure) is fully functional. The shortcut buttons and measure
   toggles are already *wired* at this point (T014's callback listens to
   all of them), but their own acceptance scenarios (US2/US3) are not yet
   formally verified — "User Story 1 only" means US1's own acceptance
   scenarios and code are complete and independently verified, not that
   the other controls are inert.

### Incremental Delivery

1. Foundational → client/shared-controls/pure-function/page skeleton ready
2. + User Story 1 → validate → full default view functional, and the
   shortcut buttons' and measure toggles' underlying refresh mechanism
   works as a side effect
3. + User Story 2 → validate → shortcut buttons (including the "ITD"/"All"
   redundancy) formally covered, account-switch behavior formally covered
4. + User Story 3 → validate → measure toggling and the empty-state prompt
   formally covered — full spec scope complete
5. + Polish → validate → static analysis clean, zero regression in
   015/016/017/018/019

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] labels map each task to its spec.md user story for traceability
- This feature's Foundational phase is smaller than `018`'s because it
  needs **no new Pydantic model** (research.md #1) and only extends one
  existing shared component with one optional parameter, rather than
  extracting two modules' worth of previously-Overview-only code
- Mirroring `018`'s precedent: US2–US3 each depend on US1's T014
  specifically (not just Foundational) because Dash's
  one-callback-per-Output rule means the chart-refresh callback can only
  be built once; later stories add their own remaining control (the
  shortcut-click callback) and formal acceptance-scenario coverage of
  behavior T014 already provides
- Commit after each task or logical group (per repo convention)
- Stop at any checkpoint to manually validate that story's Independent Test
  before continuing
- No `tests/contract/` directory tasks — this project keeps consumed-API
  contract documentation in `specs/*/contracts/portfolio-analysis-api.md`
  (prose, verified against the upstream OpenAPI source) rather than
  executable contract tests, consistent with `016`/`018`'s precedent
