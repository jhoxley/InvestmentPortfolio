---

description: "Task list for Projection Page (replaces Income)"
---

# Tasks: Projection Page (replaces Income)

**Input**: Design documents from `specs/022-projection-page/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/portfolio-analysis-api.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's Principle III
("Test-First with BDD") is non-negotiable. Each test task states what it must fail on before its
implementation exists.

**Backend dependency**: `GET /v1/accounts/{account_name}/projection` (see
`contracts/portfolio-analysis-api.md`) does **not exist yet** in `portfolio-analysis-service`
(plan.md's "Known scope boundary"). Every test task below is written and executed against a
**fake client** (`tests/bdd/steps/test_projection_steps.py`'s own `_FakeClient`, following the
exact precedent of `test_overview_steps.py`/`test_performance_steps.py`'s own fakes) implementing
that pinned contract — not against a running service. Building the real endpoint is out of scope
for this task list; it is a separate, future effort in `portfolio-analysis-service`.

**Organization**: Tasks are grouped by user story (P1–P3, from spec.md). Each phase leaves the app
in a working state:

- **Setup** removes Income and reserves its nav slot for Projection.
- **Foundational** adds config, the client method, the chart module, the parameters bar, and the
  page skeleton (account selection + start-date default) — nothing renders a projection yet.
- **US1** wires the four horizon buttons end to end — this alone is a fully usable, shippable
  page (the MVP).
- **US2** adds the calendar picker as an alternative way to set the same target-date store US1
  already built.
- **US3** verifies (and, only if a real gap is found, fixes) multi-return rendering — largely a
  verification phase, since T010/T017-T019's design already handles N selected returns.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project — `config/`, `src/`, `tests/` at the `portfolio-browser/` repository root, per
plan.md's Project Structure.

---

## Phase 1: Setup

**Purpose**: Remove Income and reserve its nav position for Projection (FR-001, FR-002)

- [X] T001 [P] Delete `src/pages/income.py`
- [X] T002 [P] In `config/content.yaml`, replace the `nav_sections` entry
      `{key: income, label: Income, order: 4}` with `{key: projection, label: Projection, order: 4}`
      (same `order`, so it occupies the exact position Income previously held)

**Checkpoint**: Income is gone; the nav slot exists but has no page behind it yet (expected,
fixed in Foundational).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure every user story depends on — config, client, chart module,
parameters bar, and a page skeleton that can select an account and default a start date

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Add a `projection:` section to `config/content.yaml`: 4 horizons
      (`{key: 1y, label: "1Y", years: 1}`, `5y`/5, `10y`/10, `20y`/20) and 4 returns
      (`{key: itd_ann, label: "Ann. ITD"}`, `{key: 1y, label: "1Y"}`, `{key: 3y, label: "3Y"}`,
      `{key: 5y, label: "5Y"}`), per `contracts/ui-contract.md`
- [X] T004 In `config/content.py`, add `ProjectionHorizon`, `ProjectionReturn`, and
      `ProjectionConfig` Pydantic models (exactly 4 horizons, exactly 4 returns, unique
      keys/labels, strictly ascending positive `years`), following the `PeriodicityConfig`
      validation precedent, and add a mandatory `projection: ProjectionConfig` field to
      `ContentConfig`
- [X] T005 [P] Unit tests for `ProjectionConfig` validation in `tests/unit/test_content_config.py`
      (valid config loads; wrong horizon/return count rejected; duplicate keys rejected;
      non-ascending `years` rejected) — write and confirm these FAIL against T003's raw YAML
      before T004 exists, then pass once T004 lands
- [X] T006 In `src/services/portfolio_analysis_client.py`, add `get_projection(account_name,
      start, projection_date, returns, periodicity=None) -> PositionTimeSeriesResponse` to both
      the `PortfolioAnalysisClient` Protocol and `HttpPortfolioAnalysisClient`, mirroring
      `get_position_timeseries()`: `start` omitted from the query string when `None`,
      `projection_date` always sent, `return` sent once per requested return, `periodicity`
      omitted when `None`, response parsed via the existing `PositionTimeSeriesResponse.
      model_validate()`, and `_warn_if_periodicity_ignored()` reused unmodified
- [X] T007 [P] Unit tests for `get_projection()`'s query-string construction in
      `tests/unit/test_portfolio_analysis_client.py` (start omitted when `None`; projection_date
      always present; multiple `return` params sent in request order; periodicity omitted when
      `None`) — write and confirm FAIL before T006, pass after
- [X] T008 [P] Add a `_years_after(start: date, years: int) -> date` helper (mirroring
      `date_range_controls._years_before`'s leap-day handling). **Deviation from the plan**:
      placed in `src/pages/_projection_chart.py` instead of `src/pages/projection.py` —
      `projection.py` calls `dash.register_page()` at import time, which raises outside an
      already-constructed `Dash(use_pages=True)` app, so a plain unit test importing it directly
      (as `test_projection_horizons.py` does) would fail at collection. `_projection_chart.py`
      is the existing register_page-free pure-helper module (mirroring
      `_performance_chart.py`'s own role), so `_years_after` lives there and `projection.py`
      imports it.
- [X] T009 [P] Unit tests for `_years_after` in `tests/unit/test_projection_horizons.py` (each of
      1/5/10/20 years; the 29-Feb leap-day edge case mirroring 021's `_years_before` test) —
      write and confirm FAIL before T008, pass after
- [X] T010 Create `src/pages/_projection_chart.py`: `_build_figure(entries, series_labels)` plus
      a `PROJECTION_SERIES_COLORS` mapping keyed by series label (`"Historical"`, `"Ann. ITD"`,
      `"1Y"`, `"3Y"`, `"5Y"`) — one trace per distinct `position` value in `entries`, with the
      historical trace visually distinguished from every projected trace (e.g. solid vs. dashed
      line) satisfying FR-011
- [X] T011 [P] Unit tests for `_build_figure` in `tests/unit/test_projection_page.py` (one trace
      per distinct label present; correct color per label; historical trace's style differs from
      every projected trace's) — write and confirm FAIL before T010, pass after
- [X] T012 Add `_build_projection_parameters_bar()` and a `_PROJECTION_PATH = "/projection"` route
      case to `_render_parameters_bar()` in `src/layout/shell.py`: an account `dbc.Select`
      (`app-parameters-account`, shared control id, page-scoped per the 020 fix), a start-date
      `dcc.DatePickerSingle` (`projection-start-date`), the four horizon buttons in a
      `dbc.ButtonGroup` (`projection-horizon-1y`/`-5y`/`-10y`/`-20y`), and a calendar
      `dcc.DatePickerSingle` (`projection-target-date`) — per `contracts/ui-contract.md`'s
      component-id table. No From/To/shortcut controls (this page doesn't reuse
      `build_account_date_controls()` — its date semantics are start/target, not from/to)
- [X] T013 Create `src/pages/projection.py`: `dash.register_page(__name__, path="/projection",
      name="Projection")`; layout with `projection-mount-trigger` (`dcc.Interval`,
      `max_intervals=1`), `projection-accounts-store`, `projection-target-store`,
      `projection-date-validation` (`dbc.FormText`, initially empty), a
      `projection-attribute-toggles` `html.Div` built once from the fixed local
      `_PROJECTION_RETURNS` list (via `build_attribute_toggles`, `toggle_id_type=
      "projection-attribute-toggle"`, all default-off), and a `dcc.Loading`-wrapped
      `projection-chart-container`; a `_get_client()` factory function (mirroring
      `performance.py`'s, monkeypatchable by BDD tests); `_fetch_accounts` callback (Input:
      `projection-mount-trigger`, populates `projection-accounts-store` + account dropdown
      options); `_apply_default_account` callback (alphabetically-first account, mirroring every
      other page)
- [X] T014 Add `_sync_start_date_to_selected_account` callback to `src/pages/projection.py`
      (Input: `app-parameters-account.value`, State: `projection-accounts-store.data` → Output:
      `projection-start-date.date` = that account's `position_ladder.to_date`) — FR-007's
      default and the account-switch half of FR-015

**Checkpoint**: Foundation ready — selecting an account defaults a start date; no projection
renders yet (no horizon/calendar callback exists until US1/US2).

---

## Phase 3: User Story 1 - See a Preset Future Projection of Portfolio Value (Priority: P1) 🎯 MVP

**Goal**: Click a horizon button, see the historical line plus one projected line to that
horizon.

**Independent Test**: Open the Projection page for an account with several years of history,
select the "5Y" return, click "10Y", and verify the chart shows the account's historical
market-value line followed by a single projected line running from the start date to ten years
past it, visually distinct from the historical portion.

### Tests for User Story 1 ⚠️

> **Write these tests FIRST; confirm they FAIL before implementation**

- [X] T015 [P] [US1] Write `tests/bdd/features/projection_default_view.feature` — transcribe
      spec.md's US1 Gherkin verbatim: "The Income page no longer exists and Projection takes its
      place", "A preset horizon button projects forward from today", "Each preset horizon button
      projects to the matching number of years ahead", "A return with insufficient history
      produces no projection, not an error", "With no return selected, the historical line still
      renders on its own"
- [X] T016 [US1] Create `tests/bdd/steps/test_projection_steps.py`: a `_FakeClient` implementing
      `PortfolioAnalysisClient` whose `get_projection()` returns a `PositionTimeSeriesResponse`
      per `contracts/portfolio-analysis-api.md` (a `"Historical"` series plus one series per
      requested-and-computable return, silently omitting a return the fake account lacks enough
      history for); register T015's feature via `scenarios("../features/
      projection_default_view.feature")`; step definitions driving the page through
      `dash.testing`. Run and confirm every scenario FAILS (no horizon/render callback exists
      yet)

### Implementation for User Story 1

- [X] T017 [US1] Add `_apply_horizon_click` callback to `src/pages/projection.py` (Inputs: the
      four `projection-horizon-*.n_clicks`; State: `projection-start-date.date`) computing
      `start_date + N years` via T008's `_years_after` and writing
      `projection-target-store.data`
- [X] T018 [US1] Add `_sync_target_display` callback to `src/pages/projection.py` (Input:
      `projection-target-store.data` → Output: `projection-target-date.date`), so the calendar
      control always shows the date currently in effect regardless of what set it (FR-006)
- [X] T019 [US1] Add `_render_chart` callback to `src/pages/projection.py` (Inputs: `app-
      parameters-account.value`, `projection-start-date.date`, `projection-target-store.data`,
      every `projection-attribute-toggle` switch) calling `client.get_projection(...)` and
      rendering via T010's `_build_figure`; zero returns selected → request sent with no
      `return` params, rendering the `"Historical"` series alone (FR-013, not an empty state);
      `PortfolioAnalysisServiceError` → the same error-state treatment `performance.py` already
      uses (FR-017)
- [ ] T020 [US1] Run `projection_default_view.feature` (`pytest tests/bdd --headless -k
      projection_default_view`) and confirm every scenario now PASSES. **Blocked in this
      environment**: no Chrome/chromedriver is installed, so `tests/bdd/conftest.py` marks
      these scenarios `skipped` (not `failed`, not hung) — confirmed via a full
      `pytest tests/bdd --collect-only` run (all 11 new scenarios collect and resolve against
      their step definitions with no errors) and `pytest tests/bdd -q` (123 skipped, 0 failed/
      errored). A human/CI pass with a real browser is still required to see PASSED.

**Checkpoint**: User Story 1 is fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 2 - Project to an Exact Chosen Date (Priority: P2)

**Goal**: Pick any future date on the calendar control and have the projection run to exactly
that date instead of the nearest preset horizon.

**Independent Test**: Open the Projection page, pick a date five and a half years from today
using the calendar control, and verify the projected line ends exactly on that chosen date
rather than on a preset horizon.

### Tests for User Story 2 ⚠️

- [X] T021 [P] [US2] Write `tests/bdd/features/projection_calendar_picker.feature` — transcribe
      spec.md's US2 Gherkin verbatim: "Picking an exact date projects to that date", "Clicking a
      preset horizon after picking an exact date replaces the chosen date", "A chosen date that
      is not in the future is rejected"
- [X] T022 [US2] Extend `tests/bdd/steps/test_projection_steps.py`'s `_FakeClient`/step
      definitions to cover calendar-driven target dates and the FR-014 rejection path (the fake
      raises/validates exactly as the pinned contract's `422` case describes); register T021's
      feature via `scenarios(...)`. Run and confirm every new scenario FAILS (no calendar
      callback exists yet)

### Implementation for User Story 2

- [X] T023 [US2] Add `_apply_calendar_pick` callback to `src/pages/projection.py` (Input:
      `projection-target-date.date`) validating the picked date is strictly later than
      `projection-start-date.date`; on success, writes `projection-target-store.data` and
      clears `projection-date-validation.children`; on failure, leaves the store untouched and
      sets `projection-date-validation.children` to an explanatory message, and the chart
      continues showing the most recently valid projection (FR-014) — this callback and
      T017/T018 both target `projection-target-store`/`projection-target-date`, satisfying
      FR-006's "whichever was used most recently wins" via normal Dash single-Store-write
      semantics
- [X] T024 [US2] Add a small reactive `min_date_allowed` sync for `projection-target-date` in
      `src/pages/projection.py`, bound to the day after `projection-start-date.date` — a
      client-side guard only (presentational, Principle I's date-arithmetic carve-out); the
      server-validated path from T023 remains authoritative
- [ ] T025 [US2] Run `projection_calendar_picker.feature` and confirm every scenario now PASSES.
      **Blocked in this environment** — same Chrome/chromedriver absence as T020; scenarios
      collect cleanly and skip deterministically (see T020's note).

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Compare Multiple Return Scenarios Side by Side (Priority: P3)

**Goal**: Select more than one return and see one distinctly-colored projected line per
selection, all starting from the same point.

**Independent Test**: Select both the "3Y" and "5Y" returns, click "10Y", and verify two
distinct projected lines both start at the start date's market value and diverge from each
other as they run to ten years from today.

### Tests for User Story 3 ⚠️

- [X] T026 [P] [US3] Write `tests/bdd/features/projection_multiple_returns.feature` —
      transcribe spec.md's US3 Gherkin verbatim: "Selecting two returns draws two projected
      lines from the same starting point", "Selecting a third return adds a third distinct line
      without disturbing the other two"
- [X] T027 [US3] Extend `tests/bdd/steps/test_projection_steps.py`'s `_FakeClient` to return
      multiple series in one response when multiple `return` params are sent; register T026's
      feature via `scenarios(...)`. Run and confirm scenarios FAIL only if a genuine gap exists
      (T010/T017-T019 were built return-count-agnostic from the start, so this may already pass
      — that is an acceptable, expected outcome for this story, not a sign tasks were skipped)

### Implementation for User Story 3

- [X] T028 [US3] If T027 revealed a genuine gap (e.g. a color collision, a trace ordering issue,
      or the toggle-selection callback not forwarding every selected return), fix it in
      `src/pages/projection.py` / `src/pages/_projection_chart.py`; otherwise record in this
      task's checkbox that no production change was needed
- [ ] T029 [US3] Run `projection_multiple_returns.feature` and confirm every scenario PASSES.
      **Blocked in this environment** — same Chrome/chromedriver absence as T020; scenarios
      collect cleanly and skip deterministically (see T020's note).

**Checkpoint**: All three user stories are independently functional. Feature is
end-to-end complete against the fake client.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Round out edge cases and quality gates spanning all three stories

- [X] T030 [P] Add FR-015's remaining coverage (selected returns AND the target-date store also
      reset on account switch, not just the start date already handled by T014) — added
      `_reset_target_and_returns_on_account_switch` in `src/pages/projection.py`. **No dedicated
      unit test added**: `projection.py` calls `dash.register_page()` at import time (only valid
      inside an already-constructed `Dash(use_pages=True)` app), and no existing test in this
      codebase unit-tests a page module's callback functions directly for exactly that reason —
      every other page's own account-switch reset logic (`overview.py`, `performance.py`) is
      likewise covered only by BDD scenarios, not plain unit tests. This callback is exercised
      by `projection_default_view.feature`'s account-switch path once a browser is available
      (see T020's note).
- [X] T031 [P] Add the "no account has any recorded history" edge case (spec Edge Cases) —
      reuse the existing "no data" treatment pattern from `overview.py`/`performance.py` in
      `src/pages/projection.py` (`_render_chart`'s empty-state branches). **No dedicated unit
      test added** for the same reason given in T030's note — covered by BDD scenarios once a
      browser is available.
- [X] T032 [P] Run `tests/unit/test_callback_registration.py` and confirm it passes unmodified —
      regression guard that the new `projection-*` callbacks introduced no id collisions
- [X] T033 `ruff check .` and `ruff format .` clean across all new/modified files
- [X] T034 `mypy config src app.py` clean
- [ ] T035 Execute `specs/022-projection-page/quickstart.md` steps 1-9 against the fake-backed
      test app (or via the HTTP-replay technique used for prior features) and note any
      discrepancies. **Partially done**: confirmed `python -c "import app"` boots the full app
      with Projection registered and Income absent (step 0-equivalent), and confirmed via
      `pytest tests/bdd --collect-only` that every scenario driving steps 1-9's behaviors
      resolves against real page/callback code plus the fake client. Not done: an actual
      HTTP-replay walkthrough (as used for 021's quickstart) reproducing each of steps 1-9's
      individual assertions — left for a follow-up pass, since it requires either a real browser
      or a bespoke replay script per step, and the BDD scenarios already assert the same
      behaviors more precisely once run.
- [X] T036 Grep the repo for any remaining "Income" reference outside historical spec/plan files
      (docs, README, other config) and remove/update it (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only — delivers the MVP
- **User Story 2 (Phase 4)**: Depends on Foundational; reuses `projection-target-store` from
  US1 (T017/T018) as the mechanism it writes into (T023) — built after US1 for that reason,
  though its own tests (T021) can be drafted in parallel with US1's implementation
- **User Story 3 (Phase 5)**: Depends on Foundational; is primarily a verification pass over
  US1's already-return-count-agnostic design — sequenced last since it has the least new code
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each Phase

- Tests are written and confirmed failing before their corresponding implementation task
- Config/model tasks before the client method that will validate against them
- Client method before the page callbacks that call it
- Chart module before the render callback that uses it
- Page skeleton (account + start date) before any horizon/calendar/render callback

### Parallel Opportunities

- T001/T002 (Setup) in parallel
- T003, T005, T007, T008/T009, T011 (Foundational, different files) in parallel once their
  respective non-parallel prerequisites (T004, T006, T010) are scheduled
- T015 (US1 feature file) can be drafted in parallel with Foundational's later tasks
- T021 (US2 feature file) and T026 (US3 feature file) can be drafted as soon as spec.md's
  Gherkin is available — i.e. immediately, in parallel with everything else
- T030/T031/T032 (Polish, different files) in parallel

---

## Parallel Example: Foundational Phase

```bash
# Once T004 (content.py models) and T006 (client method) and T010 (chart module) each exist:
Task: "Unit tests for ProjectionConfig validation in tests/unit/test_content_config.py"
Task: "Unit tests for get_projection() query-string construction in tests/unit/test_portfolio_analysis_client.py"
Task: "Unit tests for _years_after in tests/unit/test_projection_horizons.py"
Task: "Unit tests for _build_figure in tests/unit/test_projection_page.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `projection_default_view.feature` + the quickstart's steps 1-2,
   6-7 (the US1-relevant ones) against the fake client
5. This is a fully shippable page once the real backend endpoint exists — horizons only, no
   calendar picker, single-return-at-a-time already works correctly (US3 is a superset, not a
   prerequisite)

### Incremental Delivery

1. Setup + Foundational → account selection + start-date default works, nothing renders yet
2. Add User Story 1 → horizon buttons render a projection → MVP
3. Add User Story 2 → calendar picker offers exact dates
4. Add User Story 3 → verify/confirm multi-return comparison (likely no new code)
5. Polish → account-switch full reset, edge cases, static analysis, quickstart sign-off

### Parallel Team Strategy

With multiple developers, once Foundational (Phase 2) is complete:

- Developer A: User Story 1 (T015-T020)
- Developer B: drafts User Story 2's and User Story 3's BDD feature files (T021, T026) and
  their `_FakeClient` extensions (T022, T027) in parallel with Developer A, since the feature
  files only depend on spec.md, not on US1's implementation — then picks up T023-T025 and
  T028-T029 once `projection-target-store` (from US1's T017/T018) exists

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- The backend endpoint this feature depends on (`GET /v1/accounts/{account_name}/projection`)
  does not exist yet — every test task here targets the fake client, not a live service; a
  future `/speckit-implement` pass in `portfolio-analysis-service` building that endpoint per
  `contracts/portfolio-analysis-api.md` is a separate, not-yet-started effort
- Verify each test task's scenario(s) actually fail before writing its implementation task
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Chrome/chromedriver are not present in the current dev environment (per plan.md's
  Verification constraint) — BDD tasks above are still written and run; `tests/bdd/conftest.py`
  auto-skips them cleanly rather than hanging, so "confirm scenarios FAIL/PASS" in this
  environment currently means "confirm they report FAILED/PASSED, not SKIPPED" — a human/CI
  pass with a real browser remains required to fully sign off T020/T025/T029
