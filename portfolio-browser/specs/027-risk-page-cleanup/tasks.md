---

description: "Task list for Risk Page Cosmetic Cleanup"
---

# Tasks: Risk Page Cosmetic Cleanup

**Input**: Design documents from `/specs/027-risk-page-cleanup/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included. This repo's constitution (Principle III, NON-NEGOTIABLE) requires Red-Green-Refactor with Gherkin BDD coverage for user-facing behavior, so every story below writes a failing test before its implementation task.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are given in every description

## Path Conventions

Single-project Dash app. All paths are relative to the repository root
(`C:\GitHub\JHoxley\InvestmentPortfolio\portfolio-browser`), matching plan.md's Project Structure.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before any change.

- [X] T001 Run the full existing suite (`pytest tests/unit tests/bdd`) and `ruff check` / `mypy` on `src/pages/risk.py`, `src/pages/_risk_chart.py`, `src/pages/_risk_table.py`, `src/pages/_var_controls.py`, `src/pages/_var_backtest_panel.py`, and `src/components/date_range_controls.py`, to confirm a green baseline before this feature's changes begin

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

None required. This feature is a presentation-layer cleanup confined to the files listed in
plan.md's Project Structure; each user story below touches a distinct set of files (or, where a
file is shared, the dependency is declared explicitly on the task), so there is no shared
infrastructure to build before story work can start.

**Checkpoint**: Proceed directly to Phase 3.

---

## Phase 3: User Story 1 - One Continuous Risk Page Instead of Tabs (Priority: P1) 🎯 MVP

**Goal**: Remove the `dbc.Tabs` wrapper so the return histogram and Value at Risk sections render
as one continuously scrollable page, histogram first.

**Independent Test**: Open the Risk page; confirm there is no tab control, the histogram section
appears first, and scrolling down reveals the Value at Risk section below it, both backed by live
data.

### Tests for User Story 1

- [X] T002 [P] [US1] Write a failing unit test in `tests/unit/test_risk_page.py` asserting the
  rendered `layout` contains no `dbc.Tabs`/`dbc.Tab` component, and that `risk-chart-container`
  precedes `risk-var-controls-container` in document order
- [X] T003 [P] [US1] Replace `tests/bdd/features/var_risk_tab_shell.feature` with
  `tests/bdd/features/risk_single_page.feature`, asserting: no tab control exists; the histogram
  chart/table are visible without any click; scrolling reveals the Value at Risk controls/chart/
  backtest panel below them. Update `tests/bdd/steps/test_risk_steps.py` and
  `tests/bdd/steps/test_var_risk_steps.py` step definitions accordingly (remove tab-click steps,
  add/adjust "is visible without interaction" steps)

### Implementation for User Story 1

- [X] T004 [US1] In `src/pages/risk.py`, replace the `dbc.Tabs`/`dbc.Tab` (`risk-tabs`,
  `risk-tab-histogram`, `risk-tab-var`) layout wrapper with a single `html.Div` that stacks the
  existing histogram `dbc.Row` (chart + table) first, then the existing VaR
  `html.Div`/`dbc.Row` block (stale banner, controls container, chart + backtest panel) below it.
  Every existing component id (`risk-chart-container`, `risk-table-container`,
  `risk-var-stale-banner`, `risk-var-controls-container`, `risk-var-chart-container`,
  `risk-var-backtest-panel`) MUST be preserved unchanged so no callback `Output`/`Input` wiring
  needs to change in this task (depends on T002, T003 existing and failing)
- [X] T005 [US1] Run T002 and T003; confirm both now pass, and re-run the full pre-existing Risk
  page unit + BDD suite to confirm no regressions from removing the tab wrapper

**Checkpoint**: The Risk page is a single scrollable page with no tabs; both sections render and
refresh exactly as before. User Story 1 is independently complete and testable.

---

## Phase 4: User Story 2 - Statistics Table Matches the Chart's Units (Priority: P1)

**Goal**: Format the histogram's return-based statistics (mean, median, minimum, maximum,
std_dev) as percent, matching the chart's x-axis, instead of unlabeled raw basis points.

**Independent Test**: Open the Risk page for an account with a non-zero mean return; confirm the
statistics table shows "8.08%" (or equivalent), not "808", and that it matches the chart's mean
line position; confirm count/skewness/kurtosis remain unformatted.

### Tests for User Story 2

- [X] T006 [P] [US2] Write a failing unit test in `tests/unit/test_risk_table.py` asserting
  `build_rows()` renders `mean`/`median`/`minimum`/`maximum`/`std_dev` as `"8.08%"`-style strings
  (value_bp / 100, two decimal places, `%` suffix) for a sample `HistogramStatistics`, while
  `count`/`skewness`/`kurtosis` remain plain unformatted values
- [X] T007 [P] [US2] Update `tests/bdd/features/risk_view_histogram.feature` (and its step
  definitions in `tests/bdd/steps/test_risk_steps.py`) to assert the statistics table's mean row
  value matches the chart's mean reference line position, expressed in percent with a visible `%`
  unit

### Implementation for User Story 2

- [X] T008 [US2] In `src/pages/_risk_table.py`, add a `_format_pct_bp(value_bp: float | None) ->
  str` helper (dividing by 100, formatting to two decimal places with a `%` suffix, returning the
  existing "N/A" placeholder for `None`) and apply it to the `mean`/`median`/`minimum`/`maximum`/
  `std_dev` rows in `build_rows()`; leave `count`/`skewness`/`kurtosis` untouched (depends on
  T006 existing and failing)
- [X] T009 [US2] Run T006 and T007; confirm both now pass

**Checkpoint**: The histogram's statistics table and chart agree on units. Independently complete
and testable; does not depend on User Story 1.

---

## Phase 5: User Story 3 - One Set of Range Controls, Not Two (Priority: P2)

**Goal**: Replace the Value at Risk section's own "Look-back" dropdown with the page's single
shared range control (shortcut buttons, extended with a new "2Y" option), so there is exactly one
range-selection control on the page.

**Independent Test**: Change the shared range selection once; confirm both the histogram and the
Value at Risk content update, with no second range control visible anywhere, and that selecting a
VaR-unsupported range (e.g. 3Y) still renders the histogram while the VaR section shows its
existing empty state.

**Note**: This story edits `src/pages/risk.py`'s layout/controls area, which User Story 1 also
edits. Implement after Phase 3 (User Story 1) completes to avoid merge conflicts in the same
file, even though the two stories are conceptually independent.

### Tests for User Story 3

- [X] T010 [P] [US3] Write a failing unit test in `tests/unit/test_date_range_controls.py`
  asserting a new "2Y" shortcut computes its `from_date` via the existing `_years_before(today,
  2)` helper (mirroring the 1Y/3Y/5Y/10Y cases already tested there), clamped to the account's
  earliest date exactly as the other shortcuts are
- [X] T011 [P] [US3] Write a failing unit test in `tests/unit/test_var_controls.py` asserting
  `build_controls()` no longer renders a "Look-back" `dbc.Label`/`dbc.Select` (no element with id
  `risk-var-lookback`), while confidence/units/PnL-basis/hide-degraded/show-ES controls are
  unchanged
- [X] T012 [P] [US3] Write a failing unit test in `tests/unit/test_var_risk_page.py` asserting:
  (a) `_fetch_var_data` now takes `risk-range-code-store.data` instead of
  `risk-var-lookback.value`; (b) when that code matches one of `risk-var-methods-store`'s
  reported `lookbacks[].code` values, it is passed through as the `lookback` argument exactly as
  today; (c) when it does not match (or is `None`), the callback still calls `get_var_status` but
  not `get_var_series`/`get_var_backtest`, and returns a well-formed payload with
  `series == {"series": []}` and `backtest == {}` (not `None`, and without raising
  `PreventUpdate`) — see research.md #5 / contracts/ui-contract.md point 3 for why this exact
  shape is required (the original `PreventUpdate`-plus-cleared-`Output` design was
  self-contradictory and would have left stale data on screen, per `/speckit-analyze` finding F1)
- [X] T013 [P] [US3] Update `tests/bdd/features/var_risk_refetch_controls.feature` and
  `tests/bdd/features/var_risk_chart.feature` (and their steps in
  `tests/bdd/steps/test_var_risk_steps.py`) to assert: clicking any shared shortcut button
  (1Y/2Y/3Y/5Y/10Y/All) refreshes both sections; selecting 1Y/2Y/5Y refreshes the VaR chart and
  backtest panel with that look-back; selecting 3Y/10Y/All leaves the histogram rendering normally
  while the VaR section shows "No Value at Risk data is available for the selected range"

### Implementation for User Story 3

- [X] T014 [US3] In `src/pages/risk.py`, add a page-local "2Y" shortcut `dbc.Button` (id
  `risk-shortcut-2y`, code `"2y"`) next to the existing shared shortcut buttons, and a new
  `dcc.Store(id="risk-range-code-store")` alongside the page's other stores (depends on T004 from
  User Story 1 being complete)
- [X] T015 [US3] In `src/pages/risk.py`, extend `_apply_date_range_shortcut` to accept the new
  `risk-shortcut-2y` `n_clicks` Input (computing its date via the helper from T010); it needs no
  new `Output` for `risk-range-code-store` (that store is derived, not written here — see T015a).
  Add a new callback `_derive_range_code` with `Input("app-parameters-from-date", "date")`,
  `Input("app-parameters-to-date", "date")`, `State("app-parameters-account", "value")`,
  `State("risk-accounts-store", "data")` → `Output("risk-range-code-store", "data")`, which
  recomputes from the *current* from/to values which (if any) of the six shortcut codes the
  selected account's own `_shortcut_from_date`/`_last_business_day` would produce that exact
  range for today, returning the matching code or `None`. Deriving the value this way (rather
  than having a shortcut-click callback and a separate "was this a manual edit?" callback both
  try to write the same store) avoids the callback-ordering race `/speckit-analyze` flagged as
  finding F2 — see research.md #5 (depends on T014)
- [X] T016 [US3] In `src/pages/_var_controls.py`, remove the "Look-back" `dbc.Label`/`dbc.Select`
  (and the now-unused `headline`/`lookback_options` computation) from `build_controls()` (depends
  on T011 existing and failing)
- [X] T017 [US3] In `src/pages/risk.py`, change `_fetch_var_data`'s `Input("risk-var-lookback",
  "value")` to `Input("risk-range-code-store", "data")`, plus a new
  `State("risk-var-methods-store", "data")` to validate the code against the server-reported
  look-back list. When unsupported (or `None`), still call `get_var_status` but skip
  `get_var_series`/`get_var_backtest`, and `return` (not raise `PreventUpdate`) a payload shaped
  `{"account_name": account_name, "lookback_code": None, "series": {"series": []},
  "backtest": {}, "status": status_data, "fetch_error": None}` so `_render_var_view`'s existing
  empty-series branch renders the empty state with no change to that callback — per
  research.md #5 / contracts/ui-contract.md point 3's correction of finding F1 (depends on T015,
  T016)
- [X] T018 [US3] Run T010–T013; confirm all now pass, then run the existing VaR-section unit/BDD
  suite to confirm no regressions

**Checkpoint**: Exactly one range control exists on the page and drives both sections correctly,
including the VaR-unsupported fallback. Depends only on User Story 1's layout merge.

---

## Phase 6: User Story 4 - A Clear Chart With One Reference Line and a Trustworthy Scale (Priority: P2)

**Goal**: Remove the median reference line (keep only mean); lock in with a regression test that
the chart's x-axis already represents absolute return values, not offsets from the mean.

**Independent Test**: Open the Risk page for an account whose mean and median differ; confirm only
one reference line (mean) is drawn, and that the statistics table's minimum/maximum align with the
chart's leftmost/rightmost populated bars on its percent-labelled axis.

### Tests for User Story 4

- [X] T019 [P] [US4] Write a failing unit test in `tests/unit/test_risk_chart.py` asserting
  `build_figure()`'s returned figure contains exactly one `vline`/shape annotated "Mean" and none
  annotated "Median"
- [X] T020 [P] [US4] Write a new regression unit test in `tests/unit/test_risk_chart.py` asserting
  that for a histogram response where the mean/median are non-zero, a bucket with a known raw
  basis-point center (e.g. `-150`) renders at x = `-1.5` on the figure — independent of the
  mean/median values — proving the axis is absolute-scale, not mean-relative

### Implementation for User Story 4

- [X] T021 [US4] In `src/pages/_risk_chart.py::build_figure`, delete the median
  `fig.add_vline()` call; leave the mean `fig.add_vline()` call and all bucket-coloring logic
  unchanged (depends on T019 existing and failing)
- [X] T022 [US4] Run T019 and T020; confirm both now pass

**Checkpoint**: The chart shows one unambiguous reference line and its axis-scale correctness is
now regression-tested. Independently complete; does not depend on any other story.

---

## Phase 7: User Story 5 - Matching Visual Style for Both Statistics Summaries (Priority: P3)

**Goal**: Restyle the Value at Risk backtest panel to use the same `dash_table.DataTable`
presentation as the histogram's statistics table.

**Independent Test**: Compare the histogram's statistics table with the Value at Risk backtest
summary; confirm both use the same typography, borders/spacing, and header styling.

### Tests for User Story 5

- [X] T023 [P] [US5] Write a failing unit test in `tests/unit/test_var_backtest_panel.py`
  asserting `build_panel()` returns (or contains) a `dash_table.DataTable`-shaped structure using
  the same `style_cell`/`style_header` dictionaries as `risk.py`'s `risk-statistics-table`, rather
  than `html.H6`/`html.P` blocks
- [X] T024 [P] [US5] Update `tests/bdd/features/var_risk_backtest_panel.feature` (and its steps)
  to assert the panel renders as a labelled table/grid matching the histogram table's visual
  treatment, preserving all existing figures (exceptions vs. expected, Kupiec/conditional-coverage
  p-values, zone, mean VaR, VaR stability)

### Implementation for User Story 5

- [X] T025 [US5] Rebuild `src/pages/_var_backtest_panel.py::build_panel`/`_level_block` to render
  each confidence level's figures via `dash_table.DataTable`, reusing the exact `style_cell`/
  `style_header` dictionaries `risk.py` defines for `risk-statistics-table`, with no change to
  which figures are shown or their values (depends on T023 existing and failing)
- [X] T026 [US5] Run T023 and T024; confirm both now pass

**Checkpoint**: Both statistics presentations share one visual style. Independently complete; does
not depend on any other story.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all five stories together.

- [X] T027 [P] Run `ruff check` and `mypy` across all files touched by this feature
  (`src/pages/risk.py`, `src/pages/_risk_chart.py`, `src/pages/_risk_table.py`,
  `src/pages/_var_controls.py`, `src/pages/_var_backtest_panel.py`,
  `src/components/date_range_controls.py`)
- [X] T028 Run the full `pytest tests/unit tests/bdd` suite and confirm all tests (pre-existing and
  new) pass together
- [X] T029 Update `src/pages/risk.py`'s module docstring (lines 1–26) to describe the merged
  single-page layout and the shared range-control callback graph, replacing the now-outdated
  references to a "Value at Risk" tab and the `risk-var-lookback` dropdown
- [ ] T030 Walk through `specs/027-risk-page-cleanup/quickstart.md` end-to-end against a running
  `portfolio-analysis-service` account with a completed VaR calculation, confirming every step
- [X] T031 Diff this feature's full changeset against `main` and confirm no file under a
  `portfolio-analysis-service` path, or any calculation/aggregation logic, was touched — only the
  presentation-layer files listed in plan.md's Project Structure (spec.md FR-011)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: None for this feature — proceed directly to Phase 3
- **User Story 1 (Phase 3)**: No dependencies on other stories — start after Phase 1
- **User Story 2 (Phase 4)**: No dependencies on other stories — start after Phase 1, any time
  (different files than US1)
- **User Story 3 (Phase 5)**: Depends on User Story 1 (Phase 3) being complete — shares
  `src/pages/risk.py`'s layout/controls area
- **User Story 4 (Phase 6)**: No dependencies on other stories — start after Phase 1, any time
  (different files than US1/US2/US3)
- **User Story 5 (Phase 7)**: No dependencies on other stories — start after Phase 1, any time
  (different files than all others)
- **Polish (Phase 8)**: Depends on all five user stories being complete

### Within Each User Story

- Tests MUST be written and FAIL before the corresponding implementation task
- Implementation task(s) follow, then a final "run tests, confirm green" task

### Parallel Opportunities

- T001 (Setup) runs alone first
- Once T001 completes: User Stories 1, 2, and 4 can start in parallel immediately (disjoint
  files); User Story 5 can also start in parallel (disjoint files)
- User Story 3 must wait for User Story 1's T004 to land, then proceeds independently of US2/US4/US5
- All test-writing tasks marked `[P]` within a story can run in parallel with each other (they
  touch different test files)

---

## Parallel Example: Phase 1 Complete, Stories Starting

```bash
# After T001, launch these story kick-offs in parallel (different files each):
Task: "Write failing unit test for no dbc.Tabs in tests/unit/test_risk_page.py" (US1, T002)
Task: "Write failing unit test for percent-formatted stats in tests/unit/test_risk_table.py" (US2, T006)
Task: "Write failing unit test for single mean vline in tests/unit/test_risk_chart.py" (US4, T019)
Task: "Write failing unit test for DataTable-styled backtest panel in tests/unit/test_var_backtest_panel.py" (US5, T023)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 3: User Story 1 (single page, no tabs)
3. **STOP and VALIDATE**: confirm the merged page renders both sections correctly
4. This alone delivers the most visible structural change the user asked for

### Incremental Delivery

1. Setup → User Story 1 (merged page) → validate → demo
2. Add User Story 2 (unit-matched table) → validate → demo — fixes the "is 8.08 really 0.0808%?"
   trust problem
3. Add User Story 3 (single range control) → validate → demo — requires US1 complete
4. Add User Story 4 (mean-only line + axis regression test) → validate → demo
5. Add User Story 5 (matching visual style) → validate → demo
6. Polish (Phase 8) once all five are in

### Suggested Order Given Priorities

Spec.md marks US1 and US2 as P1, US3 and US4 as P2, US5 as P3. Since US1/US2/US4/US5 are mutually
independent (disjoint files), they may be done in any order or in parallel; only US3 has a hard
ordering constraint (after US1). A sensible single-developer sequence: **US1 → US2 → US4 → US3 →
US5 → Polish**, front-loading the two P1 stories and the only cross-story dependency before the
lower-priority polish item.

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependency — safe to run in parallel
- `[Story]` labels map every Phase 3–7 task to its spec.md user story for traceability
- Every implementation task names the exact test task(s) it must make pass
- No task introduces a new file beyond what plan.md's Project Structure lists — this is a
  cleanup of existing modules, not new functionality
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently before moving on
