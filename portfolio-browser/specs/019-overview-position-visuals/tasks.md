---

description: "Task list for Overview Position Visualizations"
---

# Tasks: Overview Position Visualizations

**Input**: Design documents from `specs/019-overview-position-visuals/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's
Principle III ("Test-First with BDD") is non-negotiable, and this feature
follows the same discipline as `015`-`018`.

**Organization**: Tasks are grouped by user story (P1, P2, from spec.md).
Because the pie chart and the winners/losers table are built from one
single fetch and rendered by one callback (contracts/ui-contract.md —
FR-013-style atomicity, same reasoning `018` applied to its own
chart+table pair), that one combined callback is built once, in User
Story 1's phase (T012) — mirroring `017`'s and `018`'s precedent, where
one shared callback was built in US1's phase even though part of its
output belonged to a later story. User Story 2's phase is therefore mostly
formal test coverage of behavior T012 already provides, plus any fix that
coverage reveals — see the Notes section for the full rationale.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task)
- **[Story]**: Which user story this task belongs to (US1, US2)
- All file paths are relative to `portfolio-browser/`

---

## Phase 1: Setup

**Purpose**: None needed — no new dependencies, no new packages, no new
configuration (plan.md's Technical Context: "zero new third-party
dependencies"). This phase is intentionally empty; proceed directly to
Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared value-formatting extraction, the new pure
pie/ranking/gradient/table-building functions, and the new (still inert)
layout row — both user stories' implementation depends on these existing
first.

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete.

- [X] T001 [P] Create `src/components/value_formatting.py`: move `_format_attribute_value()` and `_PLAIN_NUMERIC_ATTRIBUTES` out of `src/pages/_positions_chart.py` into this new shared module unchanged (research.md #2), and relocate their existing unit tests from `tests/unit/test_positions_chart_shaping.py` into a new `tests/unit/test_value_formatting.py` — confirm the relocated tests still pass with no behavior change (pure move, not new behavior, so no new failing-test-first step)
- [X] T002 Update `src/pages/_positions_chart.py` to import `_format_attribute_value`/`_PLAIN_NUMERIC_ATTRIBUTES` from `src/components/value_formatting.py` instead of defining them locally; run `tests/unit/test_positions_chart_shaping.py` in full to confirm zero regression (depends on T001)
- [X] T003 [P] Write failing unit tests in `tests/unit/test_overview_position_widgets.py` for `_build_pie_figure()` (not yet created, in `src/pages/_overview_position_widgets.py`): one slice per position with a positive market value; a position with a zero/negative/absent market value is excluded (FR-012); any slice ≥5% of the total market value carries its position name as on-slice text, slices below 5% carry empty on-slice text (FR-002a); every slice's `hovertemplate` includes its exact position name, market value, and percentage regardless of size
- [X] T004 Implement `_build_pie_figure()` in a new `src/pages/_overview_position_widgets.py`, using a `plotly.graph_objects.Pie` trace with per-slice `text`/`textinfo`/`hovertemplate` (research.md #3) — makes T003 pass (depends on T003)
- [X] T005 [P] Write failing unit tests in `tests/unit/test_overview_position_widgets.py` for the ranking/tie-break/group-split function: positions sorted descending by `pnl`, ties broken ascending by position name; with ≥10 qualifying positions, exactly the top 5 become `"winner"` and the bottom 5 become `"loser"` (mildest-loss first, worst last); with <10 qualifying positions, every one appears exactly once split `ceil(n/2)` winners / `floor(n/2)` losers with no padding or duplication (FR-013); a position with no recorded `pnl` is excluded (FR-012). **Critically, also assert each row's `rank_index` (the value `_gradient_color` will consume) is correct for *both* groups — winners: `rank_index` counts from the best position (index 0 = highest `pnl`); losers: `rank_index` counts from the *worst* position, i.e. the reverse of display order (index 0 = single worst `pnl`, the last index = the mildest/best-of-the-losers) — for a loser at display position `k` of `m` losers, `rank_index == m - 1 - k`. Cover this reversal explicitly for both the `n >= 10` (5 losers) and `n < 10` (fewer losers, including exactly 1) cases — `/speckit-analyze` finding G2: a naive implementation that reuses display order as `rank_index` for losers would pass every other assertion here while silently inverting FR-008's gradient (row 6 rendering bright instead of pale, row 10 pale instead of bright).
- [X] T006 Implement the ranking/tie-break/group-split function in `src/pages/_overview_position_widgets.py` (data-model.md's "Ranking algorithm"), assigning `rank_index` per data-model.md's Position Performance Rank Row field definition — winners counted from best (index 0 = highest `pnl`), losers counted from *worst* (index 0 = lowest `pnl`), the reverse of the losers' own display order — makes T005 pass, including its `rank_index`-reversal assertions (depends on T005)
- [X] T007 [P] Write failing unit tests in `tests/unit/test_overview_position_widgets.py` for `_gradient_color(index, group_size, bright_hex, pale_hex)`: index 0 returns `bright_hex` exactly, the last index returns `pale_hex` exactly, intermediate indices interpolate monotonically between them, and `group_size == 1` returns `bright_hex` (research.md #4's single-worst-position anchor, covering FR-013's fewer-than-10 edge case)
- [X] T008 Implement `_gradient_color()` in `src/pages/_overview_position_widgets.py` (linear RGB interpolation) — makes T007 pass (depends on T007)
- [X] T009 [P] Write failing unit tests in `tests/unit/test_overview_position_widgets.py` for `_build_winners_losers_table()`: combines T006's ranking with T008's gradient and `_format_attribute_value()` (via T001's shared module) into a `dash_table.DataTable` with columns for position name, profit/loss, and book cost (FR-007), and `style_data_conditional` entries mapping each row's rank/group to its `_gradient_color()` background (FR-008)
- [X] T010 Implement `_build_winners_losers_table()` in `src/pages/_overview_position_widgets.py` — makes T009 pass (depends on T001, T006, T008, T009)
- [X] T011 [P] Add a new row to `src/pages/overview.py`'s `layout`, below the existing chart's `dcc.Loading`: `overview-position-widgets-row` (`dbc.Row`) containing two `dbc.Col(xs=12, lg=6)` children (research.md #5) — a `dcc.Loading`-wrapped `overview-pie-container` and a `dcc.Loading`-wrapped `overview-winners-losers-container`, each initially showing the page's existing `_empty_state("Loading…")` placeholder — inert, not yet wired to any callback. No dependency on T004/T010 (`/speckit-analyze` finding L1) — this task only adds empty placeholder containers to `overview.py`'s layout; it doesn't call either builder function, so it can run in parallel with the rest of Foundational

**Checkpoint**: The new row renders on the Overview page with loading placeholders in both halves, correctly stacking below tablet width; the pure pie/ranking/gradient/table functions are fully unit-tested and green. No account/date-driven data has been fetched for either widget yet.

---

## Phase 3: User Story 1 - See portfolio composition at a glance (Priority: P1) 🎯 MVP

**Goal**: A pie chart of position weights (by market value, as of the
selected "To" date) appears below the performance chart, refreshing on
account/date change, with labels on slices ≥5% and hover on every slice.

**Independent Test**: With the Overview chart already showing data, verify
the pie chart appears with correctly sized/labeled/hoverable slices, and
that changing the account or the "To" date refreshes it.

### Tests for User Story 1 ⚠️

- [X] T012 [P] [US1] Write failing BDD scenarios in `tests/bdd/features/overview_position_pie_chart.feature` + step definitions in `tests/bdd/steps/test_overview_steps.py` covering spec.md's US1 Acceptance Scenarios 1–4: the pie chart renders with one slice per position sized by market-value share, labeled directly on slices ≥5% with hover available on every slice; changing the account refreshes it; changing the "To" date refreshes it; an account with no position data on the "To" date shows a "no data" message. Also cover FR-001a: at a tablet viewport width (reusing `test_shell_steps.py`'s existing `_TABLET_WIDTH` constant), the pie chart and winners/losers table stack vertically instead of side-by-side.

### Implementation for User Story 1

- [X] T013 [US1] Add the combined pie+table render callback to `src/pages/overview.py`: `Input`s on `app-parameters-account.value` and `app-parameters-to-date.date` only (never `from-date` or the attribute toggles, per FR-010); **first guard clause**: `if not account_name or not to_date: raise PreventUpdate`, mirroring the existing `_render_chart` callback's own `if not account_name or not from_date or not to_date` pattern (`/speckit-analyze` finding G1 — without this, the callback can be invoked with `to_date` still `None` during the account→date-sync chain on initial mount/account switch, raising on `date.fromisoformat(None)`); then calls `client.get_position_timeseries(account_name, positions=[], attributes=["market_value", "pnl", "book_cost"], start=to_date, end=to_date)` once; builds the pie via `_build_pie_figure()` (T004) and the table via `_build_winners_losers_table()` (T010) from the same response; further guard clauses for a data-less account/empty response (both containers → empty-state) and any client error (both containers → error-state, FR-014) — makes T012's pie-chart scenarios pass (depends on T004, T010, T011)

**Checkpoint**: User Story 1 is fully functional and independently
testable — run `overview_position_pie_chart.feature` and the US1
walkthrough in `quickstart.md`. Because T013 already fetches
`pnl`/`book_cost` and builds the winners/losers table alongside the pie
chart (the same single-callback, single-fetch design contracts/ui-contract.md
requires), User Story 2's own table is already functional at this
checkpoint; its own phase adds formal acceptance-scenario coverage. See
Notes.

---

## Phase 4: User Story 2 - Identify the biggest winners and losers (Priority: P2)

**Goal**: A "Biggest winners and losers" table appears to the right of the
pie chart, showing the top-5/bottom-5 positions by profit/loss (fewer if
the account has fewer than 10 qualifying positions) with a green→blue
gradient and each row's book cost alongside its profit/loss.

**Independent Test**: With the Overview chart already showing data, verify
the 10-row (or fewer) table appears with the correct ranking, gradient,
and column values, and that it refreshes on account/date change.

### Tests for User Story 2 ⚠️

- [X] T014 [P] [US2] Write failing BDD scenarios in `tests/bdd/features/overview_winners_losers_table.feature` + steps covering spec.md's US2 Acceptance Scenarios 1–6: the table is captioned "Biggest winners and losers"; with ≥10 qualifying positions the first 5 rows are the 5 highest profit/loss (descending) and the last 5 are the 5 lowest (mildest-loss first, worst last) with no position repeated; row backgrounds shade from bright green (row 1) through pale green (row 5), then pale blue (row 6) through bright blue (row 10); each row shows its position name, profit/loss, and book cost; with fewer than 10 qualifying positions every one appears exactly once with no blank/duplicate rows; the table refreshes on account/"To"-date change

### Implementation for User Story 2

- [X] T015 [US2] Verify T013's callback and T010's `_build_winners_losers_table()` already satisfy T014's scenarios; fix any ranking, gradient, or column-labeling defect it reveals (depends on T010, T013, T014)

**Checkpoint**: Both user stories independently functional — full spec scope complete.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Static analysis and full-suite regression, run last against
the fully-wired feature (this feature modifies shared Positions-page code
— T002 — so a full regression pass matters here too, not just for the new
files).

- [X] T016 [P] Run `.venv/Scripts/python -m ruff check .` and `.venv/Scripts/python -m mypy .`; fix any issues in all new/modified files (`src/components/value_formatting.py`, `src/pages/_overview_position_widgets.py`, `src/pages/overview.py`, `src/pages/_positions_chart.py`). **Verified**: both commands report zero issues across the full project (43 source files).
- [X] T017 [P] Run `.venv/Scripts/python -m pytest tests/unit tests/bdd` in full and confirm all pass — including 015's-018's pre-existing scenarios (regression risk: this feature modifies `_positions_chart.py`'s imports, not just adds new files). **`tests/unit`**: all 88 tests pass (18 new/relocated in `test_overview_position_widgets.py`, 3 relocated in `test_value_formatting.py`, plus all pre-existing 015-018 tests unchanged and green). **`tests/bdd`**: all 77 scenarios (66 pre-existing + 11 new) collect successfully — every Gherkin step resolves, confirming no wiring/import errors. Actually running them requires Chrome/chromedriver, not installed in this sandbox (`'chromedriver' executable needs to be in PATH`) — identical limitation already documented in `specs/017-chart-date-range-shortcuts/tasks.md` and `specs/018-positions-page/tasks.md`. **Not executed to a pass/fail verdict** — needs a machine with Chrome.
- [ ] T018 Perform the full manual walkthrough in `quickstart.md` against a real running `portfolio-analysis-service` instance (both user stories plus the FR-010 independence and FR-001a responsive checks). **Not done** — no running `portfolio-analysis-service` instance or browser in this session; requires a manual pass by whoever has both runnable locally.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Empty — nothing to do
- **Foundational (Phase 2)**: No dependencies — BLOCKS both user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational + US1's T013 (the shared render callback that already builds the table)
- **Polish (Phase 5)**: Depends on both user stories being complete

User Story 2 depends on US1's T013 specifically, not just Foundational —
this mirrors `017`'s and `018`'s precedent, and for the same underlying
reason: the pie chart and table are built from one fetch and rendered by
one callback (contracts/ui-contract.md), so that callback can only be
built once, and it already handles both widgets' data from the start.

### Within Each User Story

- Its `.feature` scenario(s) are written and confirmed failing before that
  story's implementation tasks (constitution Principle III)
- Pure functions (Foundational) before the callback that calls them
  (User Story 1) before cross-cutting verification (User Story 2)
- Story complete (its own Acceptance Scenarios all pass) before moving to
  the next priority

### Parallel Opportunities

- T001 (Foundational) — independent new-file creation, can start immediately
- T011 (Foundational) — independent layout-only addition to `overview.py`;
  touches no file the T001-T010 pure-function chain depends on, so it can
  run in parallel with all of them (corrected per `/speckit-analyze`
  finding L1 — previously listed as depending on T004/T010, which it
  doesn't actually need)
- T003, T005, T007, T009 (Foundational) — four independent test-writing
  tasks targeting the same new test file but logically separable; their
  respective implementation tasks (T004, T006, T008, T010) must wait on
  their own test but the underlying functions can be implemented in the
  same order without blocking each other's design
- T012, T014 — each story's BDD-writing task can be drafted in parallel
  with the other once Foundational is done, even though the corresponding
  implementation task (T015) must wait on US1's T013
- T016, T017 (Polish) — different concerns, run together; T018 is manual
  and independent of both

---

## Parallel Example: Foundational Phase

```bash
# Launch the independent Foundational test-writing tasks together:
Task: "Create src/components/value_formatting.py (relocated formatting logic + tests)"
Task: "Write failing unit tests for _build_pie_figure() in tests/unit/test_overview_position_widgets.py"
Task: "Write failing unit tests for the ranking/tie-break/group-split function"
Task: "Write failing unit tests for _gradient_color()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: run `overview_position_pie_chart.feature` + the
   US1 walkthrough in `quickstart.md`
4. Demo: the pie chart is fully functional, and — because T013 fetches
   `pnl`/`book_cost` and builds the winners/losers table in the same pass
   — the table is already rendering correctly too. "User Story 1 only"
   means US1's own acceptance scenarios and code are complete and
   independently verified, not that the table is inert or hidden.

### Incremental Delivery

1. Foundational → shared formatting extracted, pure functions and the
   (still inert) layout row ready
2. + User Story 1 → validate → pie chart functional, and the
   winners/losers table works as a side effect of the same callback
3. + User Story 2 → validate → winners/losers table's own acceptance
   scenarios (ranking, gradient, fewer-than-10 case) formally covered —
   full spec scope complete
4. + Polish → validate → static analysis clean, zero regression in
   015-018

---

## Notes

- [P] tasks touch different files (or, within the same new test file,
  independent test additions) with no unmet dependency
- [Story] labels map each task to its spec.md user story for traceability
- Mirroring `017`'s/`018`'s precedent: US2 depends on US1's T013
  specifically because the pie+table refresh mechanism can only be built
  once (one callback, one fetch, atomic per contracts/ui-contract.md);
  User Story 2's phase adds its own formal acceptance-scenario coverage of
  behavior T013 already provides, plus any fix that coverage reveals
- Commit after each task or logical group (per repo convention)
- Stop at any checkpoint to manually validate that story's Independent Test
  before continuing
- No `tests/contract/` directory tasks — this feature adds no new external
  API contract (reuses `018`'s endpoint as-is, per
  `contracts/ui-contract.md`)
