---

description: "Task list for Value at Risk Chart Cosmetic Fixes"
---

# Tasks: Value at Risk Chart Cosmetic Fixes

**Input**: Design documents from `/specs/028-var-chart-cosmetic-fixes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included. This repo's constitution (Principle III, NON-NEGOTIABLE) requires Red-Green-Refactor with Gherkin BDD coverage for user-facing behavior, so every story below writes a failing test before its implementation task.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are given in every description

## Path Conventions

Single-project Dash app. All paths are relative to the repository root
(`C:\GitHub\JHoxley\InvestmentPortfolio\portfolio-browser`), matching plan.md's Project Structure.

---

## Phase 1: Setup

**Purpose**: Confirm a clean baseline before any change.

- [X] T001 Run the full existing suite (`pytest tests/unit tests/bdd`) and `ruff check` /
  `mypy` on `src/pages/_var_chart.py` and `src/pages/_var_backtest_panel.py`, to confirm a
  green baseline before this feature's changes begin

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

None required. Every story below is a presentation-only change confined to one of two
existing helper modules; see the per-story file-overlap note for the one real ordering
constraint (US1/US3/US4 all touch `_var_chart.py`).

**Checkpoint**: Proceed directly to Phase 3.

---

## Phase 3: User Story 1 - See the Backtest Summary Without It Being Pushed Off-Screen (Priority: P1) 🎯 MVP

**Goal**: Move the chart's legend below the whole figure so it no longer overlaps the
space the backtest panel column needs.

**Independent Test**: Open the Value at Risk section; confirm the legend renders below
the chart (not inside or beside the plot area) and the backtest panel is fully visible.

### Tests for User Story 1

- [X] T002 [P] [US1] Write a failing unit test in `tests/unit/test_var_chart.py` asserting
  `build_figures(...)`'s returned figure has `layout.legend.orientation == "h"`,
  `layout.legend.xanchor == "center"`, `layout.legend.x == 0.5`, and `layout.legend.y < 0`
  (below the plot area). Do not assert a specific magnitude threshold beyond `< 0`:
  Plotly's legend `y` is relative to the whole figure's paper space regardless of subplot
  row count, so this chart's two-row figure needs the same `y` as every other chart's
  single-row figure, not a more-negative one (research.md #1, corrected per
  `/speckit-analyze` finding F1)
- [X] T003 [P] [US1] Update `tests/bdd/features/var_risk_chart.feature` (and its steps in
  `tests/bdd/steps/test_var_risk_steps.py`) to add a scenario asserting the legend element
  renders below the chart's plotting area and the backtest panel element is fully within
  the viewport (not clipped or requiring horizontal scroll)

### Implementation for User Story 1

- [X] T004 [US1] In `src/pages/_var_chart.py::build_figures`, add a `legend` kwarg
  alongside the existing `margin` kwarg in the same `fig.update_layout(...)` call:
  `legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"}` — the identical
  value used by `_performance_chart.py`/`_projection_chart.py`/`_positions_chart.py`, not a
  chart-specific one (depends on T002 existing and failing). If visual confirmation
  (T022) shows the legend rendering too close to the bottom subplot row, increase
  `margin["b"]` (currently `30`) instead of changing this `y` value.
- [X] T005 [US1] Run T002 and T003; confirm both now pass

**Checkpoint**: The legend no longer overlaps the backtest panel. Independently complete
and testable; no dependency on any other story.

---

## Phase 4: User Story 2 - One Backtest Table Instead of Up to Three (Priority: P1)

**Goal**: Replace the up-to-three per-confidence-level `DataTable`s with a single table
whose columns are the currently selected confidence levels.

**Independent Test**: With two or three confidence levels selected, confirm one table
renders with one row per statistic and one column per selected level; deselecting a level
removes its column with no other change.

### Tests for User Story 2

- [X] T006 [P] [US2] Write a failing unit test in `tests/unit/test_var_backtest_panel.py`
  asserting `build_panel(...)` with two selected confidence levels returns exactly one
  `dash_table.DataTable` (not one per level), whose `columns` are `statistic` plus one
  column per selected level (in `selected_confidence_bp`'s order), and whose six `data`
  rows match the existing statistic labels (Exceptions, Kupiec p-value, Conditional
  coverage p-value, Zone, Mean VaR, VaR stability)
- [X] T007 [P] [US2] Write a failing unit test in `tests/unit/test_var_backtest_panel.py`
  asserting that deselecting one of three confidence levels removes its column from the
  single table's `columns`/`data` without changing the remaining columns' values (compare
  the same statistic's value for the still-selected levels before and after)
- [X] T008 [P] [US2] Update `tests/bdd/features/var_risk_backtest_panel.feature` (and its
  steps) to assert the backtest panel renders as a single table with one column per
  selected confidence level, replacing the existing "The panel reflects the same
  confidence level as the chart" scenario's implicit per-level-table assumption

### Implementation for User Story 2

- [X] T009 [US2] In `src/pages/_var_backtest_panel.py`, replace `_level_rows`/`_level_block`
  and `build_panel`'s per-level loop with: a `_combined_columns(selected_confidence_bp)`
  helper building `[{"name": "statistic", "id": "statistic"}, *one column per selected
  level]` with each level column's `id` as `f"level_{confidence_bp}"` (not `pct_` — avoids
  confusion with this feature's unrelated `units == "pct"` chart-display concept, per
  `/speckit-analyze` finding F3) and `name` as the formatted confidence label (e.g.
  `"95%"`); and a `_combined_rows(levels_by_bp, selected_confidence_bp)` helper building
  the six statistic rows with one value key per selected level's column `id`; `build_panel`
  returns a single `dash_table.DataTable(columns=..., data=..., style_cell=STYLE_CELL,
  style_header=STYLE_HEADER)` wrapped in the existing `id="risk-var-backtest-panel-content"`
  `html.Div` (depends on T006, T007 existing and failing)
- [X] T010 [US2] Run T006–T008; confirm all now pass

**Checkpoint**: One combined table replaces the per-level tables. Independently complete;
different file than US1/US3/US4, so no ordering dependency on them.

---

## Phase 5: User Story 3 - A Readable Chart When Viewing Value at Risk as a Percentage (Priority: P2)

**Goal**: Hide the realised-PnL bar trace when chart units are percentage, since no
percentage-equivalent PnL field exists, so the VaR/ES forecast line's shape is readable.

**Independent Test**: Switch chart units to percentage; confirm the realised-PnL bars
disappear and the forecast line is clearly readable; switch back to money and confirm the
bars reappear exactly as before.

**Note**: Shares `src/pages/_var_chart.py` with US1 and US4. Implement after Phase 3 (US1)
to avoid merge conflicts in the same file, even though the two stories are conceptually
independent.

### Tests for User Story 3

- [X] T011 [P] [US3] Write a failing unit test in `tests/unit/test_var_chart.py` asserting
  that with `units="pct"`, `build_figures(...)`'s returned figure contains **no**
  `go.Bar` trace at all (not a `go.Bar` with `visible=False`), while the VaR overlay
  `go.Scatter` line and the linked market-value subplot traces are still present and
  unchanged
- [X] T012 [P] [US3] Write a failing unit test in `tests/unit/test_var_chart.py` asserting
  that calling `build_figures(...)` with `units="gbp"` after a prior call with
  `units="pct"` (same `series` input both times) restores the `go.Bar` trace with the same
  `y` values as an equivalent `units="gbp"`-only call — i.e. no state leaks between calls
  (this should already pass, since `build_figures` is a pure function with no shared
  state, but makes spec FR-006 an explicit regression guard)
- [X] T013 [P] [US3] Update `tests/bdd/features/var_risk_chart.feature` (and its steps) to
  add scenarios asserting that switching units to percentage hides the realised-PnL bars
  while the VaR forecast line remains visible and readable, and switching back to money
  restores the bars

### Implementation for User Story 3

- [X] T014 [US3] In `src/pages/_var_chart.py::build_figures`, wrap the existing
  `fig.add_trace(go.Bar(..., name="Realised PnL"), row=1, col=1)` call (and its
  `bar_entries`/`bar_colors` computation) in `if units == "gbp":`; when `units == "pct"`,
  skip adding the trace entirely. No other trace's construction changes (depends on T011
  existing and failing)
- [X] T015 [US3] Run T011–T013; confirm all now pass

**Checkpoint**: Percentage-mode charts no longer have a flattened forecast line. Depends
only on User Story 1's edit to the same file having already landed.

---

## Phase 6: User Story 4 - Know What Each Chart Represents (Priority: P3)

**Goal**: Add a caption above each of the chart's two subplot rows via Plotly's
`subplot_titles`, without splitting the linked, shared-x-axis chart into two components.

**Independent Test**: Open the Value at Risk section; confirm a caption appears above the
main chart and a different caption appears above the linked chart beneath it.

**Note**: Shares `src/pages/_var_chart.py` with US1 and US3. Implement after Phase 5 (US3)
to avoid merge conflicts in the same file.

### Tests for User Story 4

- [X] T016 [P] [US4] Write a failing unit test in `tests/unit/test_var_chart.py` asserting
  `build_figures(...)`'s returned figure has exactly two subplot-title annotations, the
  first containing wording about realised PnL/Value at Risk and the second containing
  wording about market value/proxied or rescaled share (inspect
  `figure.layout.annotations` for the two `make_subplots`-generated title annotations)
- [X] T017 [P] [US4] Update `tests/bdd/features/var_risk_chart.feature` (and its steps) to
  add a scenario asserting a caption element is visible directly above the main chart and
  a second, different caption element is visible directly above the linked chart

### Implementation for User Story 4

- [X] T018 [US4] In `src/pages/_var_chart.py::build_figures`, add
  `subplot_titles=["Realised PnL vs. Value at Risk forecast", "Total Market Value and
  Proxied/Rescaled Share"]` to the existing `make_subplots(rows=2, cols=1,
  shared_xaxes=True, row_heights=[0.7, 0.3], specs=[[{}], [{"secondary_y": True}]])` call;
  no other argument to `make_subplots` changes (depends on T016 existing and failing)
- [X] T019 [US4] Run T016 and T017; confirm both now pass; manually confirm (per
  quickstart.md step 8) that zooming/panning the main chart still zooms/pans the linked
  chart beneath it — `subplot_titles` must not have disturbed `shared_xaxes`

**Checkpoint**: Both chart sections are now captioned. Depends only on User Story 3's edit
to the same file having already landed.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all four stories together.

- [X] T020 [P] Run `ruff check` and `mypy` on `src/pages/_var_chart.py` and
  `src/pages/_var_backtest_panel.py`
- [X] T021 Run the full `pytest tests/unit tests/bdd` suite and confirm all tests
  (pre-existing and new) pass together
- [ ] T022 Walk through `specs/028-var-chart-cosmetic-fixes/quickstart.md` end-to-end
  against a running `portfolio-analysis-service` account with a completed VaR calculation
  and at least two confidence levels, confirming every step — including step 8's
  zoom/pan-linkage check and step 9's tablet-width check, neither of which any automated
  test in this plan covers (`/speckit-analyze` finding F2)
- [X] T023 Diff this feature's full changeset against `main` and confirm only
  `src/pages/_var_chart.py` and `src/pages/_var_backtest_panel.py` (plus their tests)
  changed — no `portfolio-analysis-service` path or calculation logic touched (spec FR-009)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: None for this feature — proceed directly to Phase 3
- **User Story 1 (Phase 3)**: No dependencies on other stories — start after Phase 1
- **User Story 2 (Phase 4)**: No dependencies on other stories — start after Phase 1, any
  time (different file than US1/US3/US4)
- **User Story 3 (Phase 5)**: Depends on User Story 1 (Phase 3) being complete — shares
  `src/pages/_var_chart.py`
- **User Story 4 (Phase 6)**: Depends on User Story 3 (Phase 5) being complete — shares
  `src/pages/_var_chart.py`
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Within Each User Story

- Tests MUST be written and FAIL before the corresponding implementation task
- Implementation task(s) follow, then a final "run tests, confirm green" task

### Parallel Opportunities

- T001 (Setup) runs alone first
- Once T001 completes: User Story 1 and User Story 2 can start in parallel immediately
  (disjoint files)
- User Story 3 must wait for User Story 1's T004 to land; User Story 4 must then wait for
  User Story 3's T014 — all three serialize through `_var_chart.py`
- All test-writing tasks marked `[P]` within a story can run in parallel with each other

---

## Parallel Example: Phase 1 Complete, Stories Starting

```bash
# After T001, launch these two independent story kick-offs in parallel:
Task: "Write failing unit test for legend position in tests/unit/test_var_chart.py" (US1, T002)
Task: "Write failing unit test for combined backtest table in tests/unit/test_var_backtest_panel.py" (US2, T006)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 3: User Story 1 (legend moved, panel no longer pushed off-screen)
3. **STOP and VALIDATE**: confirm the backtest panel is visible
4. This alone fixes the most severe (visibility-blocking) issue in this feature

### Incremental Delivery

1. Setup → User Story 1 (legend) → validate → demo — fixes the panel-visibility bug
2. Add User Story 2 (combined table) → validate → demo — can land in parallel with #1
3. Add User Story 3 (hide PnL in % mode) → validate → demo — requires US1 complete
4. Add User Story 4 (captions) → validate → demo — requires US3 complete
5. Polish (Phase 7) once all four are in

### Suggested Order Given Priorities and File Overlap

Spec.md marks US1 and US2 as P1, US3 as P2, US4 as P3. US2 is fully independent and may be
done any time; US1 → US3 → US4 must serialize through `_var_chart.py`. A sensible
single-developer sequence: **US1 → US2 → US3 → US4 → Polish**, front-loading both P1
stories before continuing down the forced `_var_chart.py` chain.

---

## Notes

- `[P]` tasks touch different files (or, within a story, different test cases in the same
  file with no shared state) and have no incomplete dependency — safe to run in parallel
- `[Story]` labels map every Phase 3–6 task to its spec.md user story for traceability
- Every implementation task names the exact test task(s) it must make pass
- No task introduces a new file beyond what plan.md's Project Structure lists — this is a
  cosmetic refinement of two existing modules, not new functionality
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently before moving on
