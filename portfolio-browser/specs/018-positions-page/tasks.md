---

description: "Task list for Positions Page"
---

# Tasks: Positions Page

**Input**: Design documents from `specs/018-positions-page/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/portfolio-analysis-api.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's
Principle III ("Test-First with BDD") is non-negotiable, and this feature
follows the same discipline as `015-create-template-python`,
`016-link-real-portfolio`, and `017-chart-date-range-shortcuts`.

**Organization**: Tasks are grouped by user story (P1–P3, from spec.md).
Because Dash allows only one callback per Output and the spec requires the
chart and table to always refresh together atomically (FR-013, SC-006),
the single combined render callback that serves every user story is built
once, in User Story 1's phase (T018) — mirroring `017`'s precedent, where
its one shared callback was built in US1's phase even though one of its
five buttons belonged to US2. Later story phases mostly add their own
distinct controls (shortcuts, the stacked-area validation callback) plus
formal test coverage of behavior the US1 callback already provides — see
the Notes section for the full rationale.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All file paths are relative to `portfolio-browser/`

---

## Phase 1: Setup

**Purpose**: None needed — no new dependencies, no new packages, no new
configuration (plan.md's Technical Context: "zero new third-party
dependencies"). This phase is intentionally empty; proceed directly to
Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The new API client/model layer, the two shared-control
extractions (research.md #1, #2), the pure chart/table-building functions,
the Positions parameters bar, and the Positions page skeleton — every user
story's implementation depends on these existing first.

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete.

- [X] T001 [P] Add `PositionSummary`, `PositionsResponse`, `PositionTimeSeriesEntry`, `PositionTimeSeriesResponse` models to `src/models/portfolio_analysis.py`, structurally parallel to the existing `TimeSeriesEntry`/`TimeSeriesResponse` but with `PositionTimeSeriesEntry` adding a `position: str` field (data-model.md's Position / Position Time Series Entry sections)
- [X] T002 [P] Write failing unit tests in `tests/unit/test_portfolio_analysis_client.py` for three new client methods — `list_account_positions(account_name)`, `list_position_attributes()`, `get_position_timeseries(account_name, positions, attributes, start, end)` — covering: successful parsing into the T001 models; `position` query params always sent as the explicit list passed in, even when it equals every known position (no "omit if all selected" special-casing, per `contracts/portfolio-analysis-api.md`'s `/speckit-analyze` remediation); 404/422/timeout all raise `PortfolioAnalysisServiceError`
- [X] T003 Implement `list_account_positions()`, `list_position_attributes()`, `get_position_timeseries()` on the `PortfolioAnalysisClient` Protocol and `HttpPortfolioAnalysisClient` in `src/services/portfolio_analysis_client.py` — makes T002 pass (depends on T001, T002)
- [X] T004 [P] Create `src/components/date_range_controls.py`: relocate `_earliest_from_date`, `_last_business_day`, `_shortcut_from_date`, and the `SHORTCUT_*` constants out of `src/pages/_overview_chart.py` into this new shared module unchanged (research.md #1), and relocate their existing unit tests from `tests/unit/test_overview_chart_shaping.py` into a new `tests/unit/test_date_range_controls.py` — confirm the relocated tests still pass with no behavior change (pure move, not new behavior, so no new failing-test-first step)
- [X] T005 [P] Add `build_account_date_controls()` to `src/components/date_range_controls.py`: the shared Account selector + "From"/"To" date pickers + 5 shortcut buttons builder, extracted from `src/layout/shell.py`'s `_build_overview_parameters_bar()`/`_build_shortcut_buttons()` (research.md #1) — same component IDs as today, unchanged behavior
- [X] T006 [P] Update `src/pages/_overview_chart.py` and `src/pages/overview.py` to import the relocated functions/constants from `src/components/date_range_controls.py` instead of defining/importing them locally; run `tests/unit/test_overview_chart_shaping.py` and `tests/bdd/features/overview_date_range_shortcuts.feature` to confirm zero regression (depends on T004)
- [X] T007 Update `src/layout/shell.py`'s `_build_overview_parameters_bar()` to call `build_account_date_controls()` from the shared module instead of building its own copy; confirm zero regression against `tests/bdd/features/overview_default_chart.feature`/`overview_switch_account.feature` (depends on T005)
- [X] T008 [P] Create `src/components/attribute_toggles.py`: `build_attribute_toggle(attribute, toggle_id_type, default_on)` + `build_attribute_toggles(attributes, toggle_id_type, default_on_names)`, extracted from `src/pages/overview.py`'s private `_attribute_toggle()` (research.md #2)
- [X] T009 Update `src/pages/overview.py` to call the shared builder from `src/components/attribute_toggles.py` instead of its own private copy; confirm zero regression against `tests/bdd/features/overview_metric_toggles.feature` (depends on T008)
- [X] T010 [P] Write failing unit tests in `tests/unit/test_positions_chart_shaping.py` for `src/pages/_positions_chart.py` (not yet created): (a) `_color_for_position()` — same name always yields the same color across repeated calls and across a fresh process (no `PYTHONHASHSEED` dependency), and 50 distinct names produce colors with a minimum hue separation; (b) `_build_figure()` — one trace per (position, attribute) pair in line mode, a shared `stackgroup` in stacked mode, each trace's color from `_color_for_position()`, and FR-016a's "Position — Attribute" legend/hover label whenever **more than one attribute is selected, regardless of position count** (including the single-position/multi-attribute case — same color, must still be distinguishable by label); (c) `_format_attribute_value()` — currency formatting for monetary attributes, plain numeric for `quantity` (FR-008a); (d) the comparison-row derivation — one row per position present in `entries`, `{attribute}`/`{attribute} (prev)` values read from the `to_date`/`from_date` entries (formatted via `_format_attribute_value()`), `"up"`/`"down"`/`"flat"` shading category from their *unformatted* numeric comparison, and a position entirely absent from `entries` produces no row (FR-025)
- [X] T011 Implement `src/pages/_positions_chart.py`: the `hashlib.sha256`-based `_color_for_position()` plus its pre-generated 50-color HSL-wheel palette (research.md #5), `_format_attribute_value()` (research.md #6a, FR-008a), `_build_figure()` for both line and stacked-area modes with the FR-016a dual-label legend/hover (triggered whenever attribute count > 1, independent of position count), and `_build_comparison_table()` returning a `dash_table.DataTable` with `style_data_conditional` mapping the shading category to light-green/light-red/unshaded backgrounds (research.md #6, FR-019) — makes T010 pass (depends on T010)
- [X] T012 [P] Update `tests/bdd/features/shell_parameters_bar_unchanged.feature`: remove `Positions` from the static-placeholder `Scenario Outline`'s `Examples` table, and add a new scenario asserting the Positions route shows real, enabled controls (mirroring the existing "The Overview route shows real controls" scenario) — confirm this new scenario fails against the current placeholder page (research.md #7)
- [X] T013 Add `_build_positions_parameters_bar()` to `src/layout/shell.py`: calls `build_account_date_controls()` (T005) plus two Positions-only controls — `positions-parameters-stacked-toggle` (`dbc.Switch`, default off) and `positions-parameters-position-filter` (`dcc.Dropdown`, `multi=True`) — and add a `/positions` branch to `_render_parameters_bar()` — makes T012 pass (depends on T005, T012)
- [X] T014 Replace the placeholder in `src/pages/positions.py` with a real page: `dash.register_page` (unchanged `path="/positions"`), layout (`positions-mount-trigger` `dcc.Interval`, three `dcc.Store`s — `positions-accounts-store`/`positions-attributes-store`/`positions-list-store`, an attribute-toggles container built via T008's shared builder, `positions-chart-container` + `positions-table-container` empty-state placeholders), and the mount-fetch callback (`GET /v1/accounts` + `GET /v1/positions/attributes` via T003, populating the account dropdown options, attribute toggles, and the two stores) — mirrors `overview.py`'s `_fetch_accounts_and_attributes` structure (depends on T003, T008, T013)
- [X] T015 [P] Add the default-account-selection callback to `src/pages/positions.py` (alphabetically-first account once `positions-accounts-store`/`positions-attributes-store` are populated), mirroring `overview.py`'s `_apply_default_account` (FR-012) (depends on T014)

**Checkpoint**: Positions route renders with real, populated-but-inert controls (account dropdown, attribute toggles, stacked-area toggle, empty position filter) and the shared Overview controls/toggles now come from the two new `src/components/` modules with zero behavior change. No position time series has been fetched yet.

---

## Phase 3: User Story 1 - See position-level performance the moment the page opens (Priority: P1) 🎯 MVP

**Goal**: Navigating to Positions shows a fully populated chart and
comparison table — first account, "YtD", all positions, default attribute
— with zero configuration.

**Independent Test**: Navigate to the Positions page from the menu on a
fresh session and verify the chart and table appear for the
alphabetically-first account's year-to-date data across all its positions,
with no manual interaction required.

### Tests for User Story 1 ⚠️

- [X] T016 [P] [US1] Write failing BDD scenarios in `tests/bdd/features/positions_default_view.feature` + step definitions in `tests/bdd/steps/test_positions_steps.py` covering spec.md's US1 Acceptance Scenarios 1–3: on first navigation, the Account selector/date range/position filter show their default selections; the chart displays the default attribute across all of the account's positions within "YtD"; an account with no recorded position data shows a clear "no data" message instead of a broken/empty chart

### Implementation for User Story 1

- [X] T017 [US1] Add the account-change callback to `src/pages/positions.py`: on `app-parameters-account.value` change, reset `app-parameters-from-date`/`to-date` to **"YtD" for that account** — computed via the shared `_shortcut_from_date(SHORTCUT_YTD, account, today)` from T004 (clamped to the account's earliest recorded date), **not** Overview's own `_sync_date_range_to_selected_account` (which yields full history — see research.md #1a; this was a `/speckit-analyze`-caught defect in the original task description) — fetch `/v1/accounts/{account}/positions` via T003, and reset `positions-parameters-position-filter.options`/`.value` to every position recorded for the new account. This one callback covers both FR-012 (fires on the initial default-account selection too, same pattern as Overview's own account-change callback) and FR-014 (fires again the same way on every later manual switch) (depends on T003, T004, T014, T015)
- [X] T018 [US1] Add the default-attribute logic to `positions.py`'s attribute-toggle rendering (`market_value` defaults on, per spec Assumptions), mirroring `overview.py`'s `_DEFAULT_METRIC` (depends on T008, T014)
- [X] T019 [US1] Add the combined chart+table render callback to `src/pages/positions.py`: `Input`s on account/from-date/to-date/attribute-toggles/position-filter/stacked-toggle; calls `get_position_timeseries()` (T003), then `_build_figure()` and `_build_comparison_table()` (T011); guard clauses — in this order — for **zero attributes selected** (`positions-empty-state`, "select at least one attribute", FR-020; mirrors Overview's existing `if not toggled_attributes` guard), a data-less account/empty response (`positions-empty-state`), and any client error (`positions-error-state`, FR-022); a `running=[...]` clause disabling every listed control for the callback's duration (FR-013, FR-023) — makes T016's default-view scenarios pass (depends on T003, T011, T017, T018)

**Checkpoint**: User Story 1 is fully functional and independently
testable — run `positions_default_view.feature` and the US1 walkthrough in
`quickstart.md`. Because T019 wires every trigger (account, date,
attribute toggles, position filter, stacked-area toggle) into one callback
— required by Dash's one-callback-per-Output rule and FR-013/SC-006's
atomicity requirement — User Stories 2–5's underlying refresh mechanism is
already functional at this checkpoint; their own phases add their
remaining distinct controls (shortcut buttons, the stacked-area validation
callback) and formal acceptance-scenario coverage. See Notes.

---

## Phase 4: User Story 2 - Explore a different account or time period (Priority: P2)

**Goal**: Switching accounts or clicking a "YtD"/"1Y"/"3Y"/"5Y"/"All"
shortcut updates the date range (and, for an account switch, the position
filter) and refreshes the chart/table accordingly.

**Independent Test**: With the Positions page loaded, switch to a
different account, then click each shortcut button in turn and verify the
"From"/"To" fields and the chart/table update correctly each time.

### Tests for User Story 2 ⚠️

- [X] T020 [P] [US2] Write failing BDD scenarios in `tests/bdd/features/positions_account_and_date_controls.feature` + steps covering spec.md's US2 Acceptance Scenarios 1–3: switching accounts resets the position filter to every position for the new account and the date range to "YtD" for that account (not its full history, per FR-014); each shortcut button updates the date fields (clamped per FR-003) and refreshes the chart/table; every listed control is disabled/has no effect while a refresh triggered by any of them is in flight

### Implementation for User Story 2

- [X] T021 [US2] Add the shortcut-click callback to `src/pages/positions.py`: five `Input(button_id, "n_clicks")`, `State` on `app-parameters-account.value` + `positions-accounts-store.data`, resolving the clicked button via `ctx.triggered_id` and computing/clamping `from_date`/`to_date` via T004's shared `_shortcut_from_date` — mirrors `overview.py`'s `_apply_date_range_shortcut` but reads from `positions-accounts-store` (depends on T004, T017)
- [X] T022 [US2] Verify T019's `running=[...]` clause already covers the shortcut buttons and the Account/From/To controls; run T020's in-flight-disabling scenario and extend the clause if it reveals a gap (depends on T019, T020, T021)

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 - Choose which measures and positions to compare (Priority: P2)

**Goal**: Toggling attributes and narrowing the position filter updates the
chart/table to exactly the selected subset; deselecting all of either
shows an empty-state prompt instead of a blank chart.

**Independent Test**: With the Positions page loaded, toggle a second
attribute on and select a subset of positions in the multi-select filter,
and verify the chart and table update to reflect exactly that selection.

### Tests for User Story 3 ⚠️

- [X] T023 [P] [US3] Write failing BDD scenarios in `tests/bdd/features/positions_attribute_and_position_filters.feature` + steps covering spec.md's US3 Acceptance Scenarios 1–4: toggling an attribute on/off updates the chart/table; selecting a position subset narrows the chart/table; zero attributes selected shows a "select at least one attribute" prompt; zero positions selected shows a "select at least one position" prompt

### Implementation for User Story 3

- [X] T024 [US3] Verify T019's callback already re-fetches on attribute-toggle/position-filter changes (both already `Input`s per `contracts/ui-contract.md`) and its zero-attributes guard fires correctly; run T023's toggle/subset scenarios and fix if needed (depends on T019, T023)
- [X] T025 [US3] Add the zero-positions-selected guard clause to T019's callback in `src/pages/positions.py` (`if not selected_positions: return positions-empty-state(...)`) — logic Overview has no equivalent of, since it has no position filter — makes T023's zero-position scenario pass (depends on T019, T023)

**Checkpoint**: User Stories 1–3 all independently functional.

---

## Phase 6: User Story 4 - Compare each position's start and current values at a glance (Priority: P2)

**Goal**: The comparison table below the chart shows one row per position
with data, a value/"(prev)" column pair per selected attribute, and
green/red/unshaded cell shading reflecting whether each value rose, fell,
or held steady.

**Independent Test**: With the Positions page loaded and a chart rendered,
verify a table appears below it with one row per plotted position, the
correct column pairs, and the correct shading for at least one risen and
one fallen position.

### Tests for User Story 4 ⚠️

- [X] T026 [P] [US4] Write failing BDD scenarios in `tests/bdd/features/positions_comparison_table.feature` + steps covering spec.md's US4 Acceptance Scenarios 1–5: one row per position with data and a value/"(prev)" column pair per selected attribute; light-green shading when the "To" value exceeds the "From" value; light-red when it's lower; unshaded when equal; the table always matches the chart's current account/date/attribute/position selection (SC-006)

### Implementation for User Story 4

- [X] T027 [US4] Verify T011's `_build_comparison_table()` and T019's wiring already satisfy T026's scenarios; fix any shading or column-labeling defect it reveals (e.g. the exact " (prev)" suffix text, FR-018) (depends on T011, T019, T026)

**Checkpoint**: User Stories 1–4 all independently functional.

---

## Phase 7: User Story 5 - Switch between a line chart and a stacked area view (Priority: P3)

**Goal**: With exactly one attribute selected, "Stacked area graph" toggles
the chart between a line chart and a stacked area chart; selecting a
second attribute while it's on automatically turns it off (never blocking
the attribute selection), and it stays disabled while more than one
attribute is selected.

**Independent Test**: With exactly one attribute selected, toggle "Stacked
area graph" on and verify the chart becomes a stacked area chart; toggle it
off and verify it reverts to a line chart.

### Tests for User Story 5 ⚠️

- [X] T028 [P] [US5] Write failing BDD scenarios in `tests/bdd/features/positions_stacked_area_toggle.feature` + steps covering spec.md's US5 Acceptance Scenarios 1–4: toggling stacked-area on with one attribute selected renders a stacked area chart; toggling it off reverts to a line chart; selecting a second attribute while it's on auto-turns it off without blocking the selection; the toggle is disabled while more than one attribute is selected

### Implementation for User Story 5

- [X] T029 [US5] Add the stacked-area validation callback(s) to `src/pages/positions.py`: an `Input` on `{"type": "positions-attribute-toggle", "name": ALL}.value` driving two `Output`s — `positions-parameters-stacked-toggle.value` (`allow_duplicate=True`, forced to `False` the instant a second attribute is toggled on, FR-010) and `positions-parameters-stacked-toggle.disabled` (`True` while more than one attribute is selected, FR-011) (depends on T013, T028)
- [X] T030 [US5] Verify T011's stacked-mode branch of `_build_figure()` renders correctly end-to-end via T019's callback once T029's toggle is wired; run T028's remaining scenarios (depends on T011, T019, T029)

**Checkpoint**: All 5 user stories independently functional — full spec scope complete.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Static analysis and full-suite regression, run last against
the fully-wired feature (this feature modifies shared Overview code —
T006, T007, T009 — so a full regression pass matters more here than in a
purely additive feature like 017).

- [X] T031 [P] Run `.venv/Scripts/python -m ruff check .` and `.venv/Scripts/python -m mypy .`; fix any issues in all new/modified files (`src/components/date_range_controls.py`, `src/components/attribute_toggles.py`, `src/pages/_positions_chart.py`, `src/pages/positions.py`, `src/pages/_overview_chart.py`, `src/pages/overview.py`, `src/layout/shell.py`, `src/models/portfolio_analysis.py`, `src/services/portfolio_analysis_client.py`). **Verified**: both commands report zero issues across the full project (39 source files).
- [X] T032 [P] Run `.venv/Scripts/python -m pytest tests/unit tests/bdd` in full and confirm all pass — including 015's, 016's, and 017's pre-existing scenarios (regression risk: this feature is the first to modify already-shipped Overview code, not just add to it). **`tests/unit`**: all 63 tests pass (21 relocated/new in `test_date_range_controls.py`, 18 new in `test_positions_chart_shaping.py`, 13 client tests incl. 6 new, plus all pre-existing 015/016/017 tests unchanged and green). **`tests/bdd`**: all 66 scenarios (43 pre-existing + 23 new) collect successfully — every Gherkin step resolves against a step definition, confirming no wiring/import errors across the whole suite, including the modified `shell_parameters_bar_unchanged.feature`. Actually running them hit `selenium.common.exceptions.WebDriverException: 'chromedriver' executable needs to be in PATH` — this sandbox has no Chrome/chromedriver installed, identical to the limitation already documented in `specs/017-chart-date-range-shortcuts/tasks.md`'s own T014. **Not executed to a pass/fail verdict** — needs a machine with Chrome, same as 017.
- [ ] T033 Perform the full manual walkthrough in `quickstart.md` against a real running `portfolio-analysis-service` instance (all 5 user stories plus the FR-023 control-disabling check). **Not done** — no running `portfolio-analysis-service` instance or browser in this session; requires a manual pass by whoever has both runnable locally.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Empty — nothing to do
- **Foundational (Phase 2)**: No dependencies — BLOCKS all 5 user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational + US1's T017 (account-change callback) and T019 (the shared render callback the shortcuts feed into)
- **User Story 3 (Phase 5)**: Depends on Foundational + US1's T019 (the callback whose `Input`s already include attribute toggles and the position filter)
- **User Story 4 (Phase 6)**: Depends on Foundational + US1's T019 (the same callback already builds the table every render)
- **User Story 5 (Phase 7)**: Depends on Foundational's T013 (stacked-toggle component) + US1's T019 (the callback whose figure-building already branches on the toggle's value via T011)
- **Polish (Phase 8)**: Depends on all 5 user stories being complete

Every user story after US1 depends on US1's T019 specifically, not just on
Foundational — this mirrors `017`'s precedent (its US2 depended on US1's
T006), and for the same underlying reason: Dash's one-callback-per-Output
rule means the chart/table refresh mechanism can only be built once, and
FR-013/SC-006 require it to already handle every trigger atomically from
the start.

### Within Each User Story

- Its `.feature` scenario(s) are written and confirmed failing before that
  story's implementation tasks (constitution Principle III)
- Client/model layer before pure functions before callbacks before
  cross-cutting verification
- Story complete (its own Acceptance Scenarios all pass) before moving to
  the next priority

### Parallel Opportunities

- T001, T002 (Foundational) — different files, run together
- T004, T008, T010 (Foundational) — three independent new-file creations, run together; their respective "make it pass"/"update caller" tasks (T003, T006/T007, T009, T011) must wait on their own prerequisite but can run in parallel with each other's *different* files once unblocked
- T012 (Foundational) — independent of the T001–T011 chain (a `.feature` file), can run any time before T013
- T015 — independent of T016 onward, can run alongside US1's test-writing (T016)
- T016, T020, T023, T026, T028 — each story's BDD-writing task can be drafted in parallel with the others once Foundational is done, even though the corresponding implementation tasks must wait on US1's T019
- T031, T032 (Polish) — different concerns, run together; T033 is manual and independent of both

---

## Parallel Example: Foundational Phase

```bash
# Launch the independent Foundational new-file/new-test tasks together:
Task: "Add PositionSummary/PositionsResponse/PositionTimeSeriesEntry/PositionTimeSeriesResponse models to src/models/portfolio_analysis.py"
Task: "Write failing unit tests for the 3 new client methods in tests/unit/test_portfolio_analysis_client.py"
Task: "Create src/components/date_range_controls.py (relocated pure functions + shared builder)"
Task: "Create src/components/attribute_toggles.py (shared toggle builder)"
Task: "Write failing unit tests for src/pages/_positions_chart.py in tests/unit/test_positions_chart_shaping.py"
Task: "Update shell_parameters_bar_unchanged.feature for the Positions route"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: run `positions_default_view.feature` + the US1
   manual walkthrough in `quickstart.md`
4. Demo: the default view (chart + table, first account, "YtD", all
   positions, default attribute) is fully functional. The shortcut
   buttons, attribute toggles, and position filter are all already
   *wired* at this point (T019's callback listens to all of them), but
   their own acceptance scenarios (US2/US3) and the stacked-area toggle's
   validation (US5) are not yet formally verified/implemented — "User
   Story 1 only" means US1's own acceptance scenarios and code are
   complete and independently verified, not that the other controls are
   inert.

### Incremental Delivery

1. Foundational → client/models/shared-controls/pure-functions/page
   skeleton ready
2. + User Story 1 → validate → full default view functional, and every
   other control's underlying refresh mechanism works as a side effect
3. + User Story 2 → validate → shortcut buttons formally covered,
   account-switch behavior formally covered
4. + User Story 3 → validate → attribute/position filtering and both
   empty-state prompts formally covered
5. + User Story 4 → validate → comparison table shading formally covered
6. + User Story 5 → validate → stacked-area toggle and its
   single-attribute constraint formally covered — full spec scope complete
7. + Polish → validate → static analysis clean, zero regression in
   015/016/017

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] labels map each task to its spec.md user story for traceability
- This feature's Foundational phase is unusually large relative to `017`'s
  because it both introduces a new page's entire data/rendering stack
  *and* extracts two modules' worth of previously Overview-only code into
  shared components — both are one-time costs paid once, not per user
  story
- Mirroring `017`'s T006/US2 precedent: US2–US5 each depend on US1's T019
  specifically (not just Foundational) because Dash's one-callback-per-Output
  rule and FR-013/SC-006's atomicity requirement mean the combined
  chart+table refresh callback can only be built once; later stories add
  their own remaining controls (shortcuts, stacked-area validation) and
  formal acceptance-scenario coverage of behavior T019 already provides
- Commit after each task or logical group (per repo convention)
- Stop at any checkpoint to manually validate that story's Independent Test
  before continuing
- No `tests/contract/` directory tasks — this project keeps consumed-API
  contract documentation in `specs/*/contracts/portfolio-analysis-api.md`
  (prose, verified against the upstream OpenAPI source) rather than
  executable contract tests, consistent with `016`/`017`'s precedent
