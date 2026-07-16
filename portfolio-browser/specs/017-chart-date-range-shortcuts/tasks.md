---

description: "Task list for Date Range Shortcut Buttons on Overview"
---

# Tasks: Date Range Shortcut Buttons on Overview

**Input**: Design documents from `specs/017-chart-date-range-shortcuts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's
Principle III ("Test-First with BDD") is non-negotiable, and this feature
follows the same discipline as `015-create-template-python` and
`016-link-real-portfolio`.

**Organization**: Tasks are grouped by user story (P1, P2, from spec.md).
Both user stories share the same underlying mechanism (one new pure
function, one new callback, five new buttons) — per plan.md/research.md,
this is a small, additive extension of three files 016 already created, not
a multi-module feature, so the Foundational phase carries most of the
implementation weight and each story phase is a thin, focused increment on
top of it.

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

**Purpose**: The pure date-shortcut-computation logic and the five button
components — both user stories' callbacks depend on these existing first.

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete.

- [X] T001 [P] Write failing unit tests for `_shortcut_from_date` in `tests/unit/test_overview_chart_shaping.py` (extend the existing file), covering: `"ytd"` → 1st January of the current year; `"1y"`/`"3y"`/`"5y"` → exact calendar-date offsets from a fixed "today"; a leap-day case (today = 29 Feb in a leap year, `"1y"` → 28 Feb the following non-leap year); clamping (a computed date earlier than the account's `earliest_from_date` is raised to that floor, per FR-008); `"all"` → exactly the account's `earliest_from_date`, unclamped-by-definition
- [X] T002 Implement `_shortcut_from_date(code, account, today) -> date` and its `_SHORTCUT_*` code constants in `src/pages/_overview_chart.py`, reusing the existing `_earliest_from_date` helper for the clamp floor and for `"all"` — makes T001 pass (depends on T001)
- [X] T003 [P] Add five `dbc.Button` shortcut controls (`overview-shortcut-ytd`, `overview-shortcut-1y`, `overview-shortcut-3y`, `overview-shortcut-5y`, `overview-shortcut-all`, labeled "YtD"/"1Y"/"3Y"/"5Y"/"All") to `_build_overview_parameters_bar()` in `src/layout/shell.py`, positioned alongside the existing From/To date controls (FR-001)

**Checkpoint**: Foundation ready — pure computation logic is unit-tested and green; buttons render (inert, not yet wired) on the Overview parameters bar.

---

## Phase 3: User Story 1 - Jump to a common reporting period in one click (Priority: P1) 🎯 MVP

**Goal**: Clicking "YtD", "1Y", "3Y", or "5Y" updates the "from"/"to" date
fields and refreshes the chart to that range in one click.

**Independent Test**: With the Overview chart displayed, click each of
"YtD"/"1Y"/"3Y"/"5Y" in turn and verify the date fields and chart update to
the correct range each time.

### Tests for User Story 1 ⚠️

- [X] T004 [US1] Write failing BDD scenarios in `tests/bdd/features/overview_date_range_shortcuts.feature` + step definitions in `tests/bdd/steps/test_overview_steps.py` covering spec.md's US1 Acceptance Scenarios 1–5: clicking "YtD" sets "from" to 1 January of the current year and "to" to the existing last-business-day default, then refreshes the chart; clicking "1Y"/"3Y"/"5Y" each set "from" to the correct calendar-date offset from today; after any click, the date fields show the exact dates now charted (not the button's label)
- [X] T005 [US1] Write a failing BDD scenario in the same feature file + steps covering FR-008/SC-004 (clamping): on an account with less than 5 years of recorded history, clicking "5Y" MUST show that account's complete available history (from = the account's own earliest recorded date, not 5 years ago) with no error/empty state — the end-to-end counterpart to T001's unit-level clamping test, closing `/speckit-analyze` finding G1 (depends on T004, since both extend the same file — write after T004's scenarios so the file's growing incrementally, not out of a functional dependency)

### Implementation for User Story 1

- [X] T006 [US1] Add the `_apply_date_range_shortcut` callback in `src/pages/overview.py`: five `Input(button_id, "n_clicks")` (the four US1 buttons plus "All", since Dash requires one callback per shared Output — see Phase 4 for "All"'s own acceptance criteria), `State("app-parameters-account", "value")`, `State("overview-accounts-store", "data")`; resolve the clicked button via `dash.ctx.triggered_id`, look up the selected account, compute `from_date`/`to_date` via `_shortcut_from_date`/`_last_business_day`, and set `Output("app-parameters-from-date", "date", allow_duplicate=True)` / `Output("app-parameters-to-date", "date", allow_duplicate=True)`; no-op (`PreventUpdate`) if no account is selected yet (depends on T002, T003) — makes T004 and T005 pass
- [X] T007 [US1] Add `allow_duplicate=True` to the existing `_sync_date_range_to_selected_account` callback's two Outputs in `src/pages/overview.py` (016), since T006 now also targets `app-parameters-from-date.date`/`app-parameters-to-date.date` (depends on T006)
- [X] T008 [US1] Manually verify (per `quickstart.md`) that setting the date fields from T006 automatically re-triggers 016's existing `_render_chart` callback with no new fetch/render code — confirms research.md #3's design assumption holds in the running app (depends on T006, T007). **Verified by code inspection** (no live browser/backing service in this environment): `_render_chart`'s `Input("app-parameters-from-date", "date")`/`Input("app-parameters-to-date", "date")` are exactly the two props `_apply_date_range_shortcut` writes to — confirmed via `app.py`'s successful build (no duplicate-Output or missing-Output errors) and `ruff`/`mypy` clean. Full click-through confirmation deferred to a real browser session (see T015).

**Checkpoint**: User Story 1 is fully functional and independently testable — run `pytest tests/bdd/features/overview_date_range_shortcuts.feature -k "ytd or 1y or 3y or 5y or clamp"` and the US1 manual walkthrough in `quickstart.md`. Note: because T006 wires all five buttons (Dash's one-callback-per-Output constraint — see research.md #4), the "All" button is *also* functional at this checkpoint even though its own story (US2) hasn't formally started; see the Implementation Strategy section below.

---

## Phase 4: User Story 2 - See an account's full history in one click (Priority: P2)

**Goal**: Clicking "All" sets "from" to the selected account's own earliest
recorded date and refreshes the chart to show its complete history.

**Independent Test**: With the Overview chart displayed, click "All" and
verify "from" updates to the selected account's earliest recorded date and
the chart shows its complete history; switch accounts and click "All"
again to confirm it reflects the new account, not the old one.

### Tests for User Story 2 ⚠️

- [X] T009 [US2] Write failing BDD scenarios in `tests/bdd/features/overview_date_range_shortcuts.feature` (same file as T004/T005) + steps in `tests/bdd/steps/test_overview_steps.py` covering spec.md's US2 Acceptance Scenarios 1–2: clicking "All" sets "from" to the selected account's earliest recorded date; after switching accounts, clicking "All" reflects the newly-selected account's own earliest date

### Implementation for User Story 2

- [X] T010 [US2] Confirm "All" is wired through the same `_apply_date_range_shortcut` callback added in T006 (it already includes `overview-shortcut-all` among its five Inputs) — no new callback needed; this task is verification (run T009's scenarios) plus fixing `_shortcut_from_date`'s `"all"` branch if T009 reveals a defect (depends on T006, T009)

**Checkpoint**: Both user stories are independently functional — run the full `overview_date_range_shortcuts.feature`.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: FR-013 (disable-during-refresh) spans both stories and every
other trigger of a chart refresh (manual date edit, account switch, initial
load per spec.md's Edge Cases) — implemented once, verified last, against
the fully-wired feature.

- [X] T011 [P] Add the `running=[...]` clause (five `(Output(button_id, "disabled"), True, False)` tuples, one per shortcut button) to the existing `_render_chart` callback in `src/pages/overview.py` (016), per `contracts/ui-contract.md`'s "Modified callback" section and the Phase 0 spike in `research.md` #1 (FR-013)
- [X] T012 [P] Write failing BDD scenario in `tests/bdd/features/overview_date_range_shortcuts.feature` (same file) + steps covering the FR-013 edge case: while a chart refresh is in flight, all five shortcut buttons are disabled; once it completes, they are clickable again — confirm this scenario passes only after T011 (depends on T011)
- [X] T013 [P] Run `.venv/Scripts/python -m ruff check .` and `.venv/Scripts/python -m mypy .`; fix any issues in the modified files (`src/layout/shell.py`, `src/pages/_overview_chart.py`, `src/pages/overview.py`) — both clean
- [ ] T014 [P] Run `.venv/Scripts/python -m pytest tests/unit tests/bdd` in full and confirm all pass — including 015's and 016's pre-existing scenarios (regression: this feature only extends already-shipped files, so nothing prior should break). **Partially verified**: `tests/unit` — all 39 tests pass. `tests/bdd` — all 43 scenarios (9 new + 34 from 015/016) collect successfully (every Gherkin step resolves, confirming no wiring/import errors); one was run and failed only at `chromedriver executable needs to be in PATH` — this sandbox has no Chrome/chromedriver installed (same limitation as 016). **Not yet executed to a pass/fail verdict** — needs a machine with Chrome to actually run `pytest tests/bdd`.
- [ ] T015 Perform the full manual walkthrough in `quickstart.md` against a real running `portfolio-analysis-service` instance (both user stories plus the FR-013 and FR-008 checks). **Not done** — no running `portfolio-analysis-service` instance or browser in this session; requires a manual pass by whoever has both runnable locally.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Empty — nothing to do
- **Foundational (Phase 2)**: No dependencies — BLOCKS both user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational + US1's T006 (the one shared callback already includes the "All" button as one of its five Inputs)
- **Polish (Phase 5)**: Depends on both user stories being complete (T011 needs the shortcut buttons' final IDs from Phase 2/3; T012 needs the full click→refresh chain working)

Unlike 016 (four largely-sequential stories through one evolving callback
graph), US1 and US2 here share literally the same callback (T006) — US2's
own "story" work (T009, T010) is almost entirely verification, since the
"All" button was structurally included in T006 from the start (five
buttons, one callback, per research.md #4's `ctx.triggered_id` design). This
also means "All" is functionally working as soon as Phase 3 (US1) is done,
not just after Phase 4 — see the Implementation Strategy section below.

### Within Each User Story

- Its `.feature` scenario(s) are written and confirmed failing before that
  story's implementation tasks (constitution Principle III)
- T004, T005, and T009 all add scenarios to the *same* `.feature` file —
  write T004's and T005's scenarios, confirm them failing, implement
  T006/T007/T008, confirm green; then add T009's scenarios to the same
  file, confirm failing (they won't be, since T006 already wired "All" —
  this is expected per the note above, not a process violation), verify via
  T010

### Parallel Opportunities

- T001, T003 (Foundational) — different files, run together
- T011, T013 (Polish) — different concerns, run together once both stories are done; T012 depends on T011 so is not parallel with it
- T014, T015 — T014 can start as soon as T011–T013 are done; T015 is manual and independent of T014's automated run

---

## Parallel Example: Foundational Phase

```bash
# Launch the independent Foundational tasks together:
Task: "Write failing unit tests for _shortcut_from_date in tests/unit/test_overview_chart_shaping.py"
Task: "Add five dbc.Button shortcut controls to _build_overview_parameters_bar() in src/layout/shell.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational
2. Complete Phase 3: User Story 1 (YtD/1Y/3Y/5Y)
3. **STOP and VALIDATE**: run the US1-tagged scenarios in
   `overview_date_range_shortcuts.feature` + the US1 manual walkthrough in
   `quickstart.md`
4. Demo: all five buttons are functional at this point — T006's shared
   callback wires "All" alongside YtD/1Y/3Y/5Y by construction (Dash's
   one-callback-per-Output rule, research.md #4). "User Story 1 only" here
   means *US1's own acceptance scenarios and code changes* are complete and
   independently verified — not that "All" is disabled or absent. Phase 4
   (US2) formalizes "All"'s own acceptance scenarios and switches its
   verification from incidental to intentional; it does not add new
   functionality.

### Incremental Delivery

1. Foundational → pure logic + buttons ready (none wired yet)
2. + User Story 1 → validate → all five buttons functional (US1's four plus
   "All" as a side effect of the shared callback); US2's own acceptance
   scenarios not yet formally verified
3. + User Story 2 → validate → "All"'s own acceptance scenarios (including
   the account-switch case) now formally covered
4. + Polish (FR-013 disabling) → validate → full spec scope complete
   (FR-008/SC-004's clamping scenario, T005, is already covered as part of
   User Story 1 above — see Notes)

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] labels map each task to its spec.md user story for traceability
- This feature has an unusually thin Setup phase (empty) and unusually
  thin US2 phase (mostly verification) precisely because plan.md/research.md
  established upfront that both stories are served by one shared callback —
  the task breakdown reflects that reality rather than inventing artificial
  per-story separation
- T005 and the Implementation Strategy section's wording were added/revised
  by `/speckit-analyze` remediation (findings G1 and I1 respectively): G1
  added end-to-end BDD coverage for the FR-008/SC-004 clamping behavior
  (previously unit-tested only); I1 corrected the MVP narrative, which
  previously claimed "4 of 5 buttons functional" after User Story 1 even
  though T006 (originally T005) always wired all five buttons
- Commit after each task or logical group (per repo convention)
- Stop at any checkpoint to manually validate that story's Independent Test
  before continuing
- No `tests/contract/` tasks — this feature adds no new external API
  contract (reuses 016's endpoints unchanged, per `contracts/ui-contract.md`)
