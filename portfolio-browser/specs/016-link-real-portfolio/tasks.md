---

description: "Task list for Account Performance Chart on Overview"
---

# Tasks: Account Performance Chart on Overview

**Input**: Design documents from `specs/016-link-real-portfolio/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, contracts/portfolio-analysis-api.md, quickstart.md

**Tests**: Included and REQUIRED, not optional — the project constitution's
Principle III ("Test-First with BDD") is explicitly non-negotiable. Every
user story phase below writes its `.feature` scenario(s) and confirms them
failing before the corresponding implementation task, matching the
discipline already used in `015-create-template-python`.

**Organization**: Tasks are grouped by user story (P1–P4, from spec.md) so
each can be implemented and manually verified independently, per its own
"Independent Test" from spec.md. Two Foundational-phase behaviors that are
not owned by any single user story (empty/error states, the non-Overview
placeholder bar staying unchanged) get their own dedicated `.feature` files
per `/speckit-analyze` findings C1/C2 — see Notes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are relative to `portfolio-browser/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new dependencies and package scaffolding this feature needs.

- [X] T001 Add `httpx>=0.27`, `plotly` (explicit, was transitive-only), and `structlog` to `dependencies` in `pyproject.toml`; reinstall with `.venv/Scripts/python -m pip install -e ".[dev]"`
- [X] T002 [P] Add `request_timeout_seconds: float = 5.0` to the `Settings` class in `config/settings.py` (alongside the existing `portfolio_analysis_service_url`), and document it in `.env.example`
- [X] T003 [P] Create `src/services/__init__.py` and `src/models/__init__.py` (new packages per plan.md's Project Structure)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The HTTP client, typed models, pure date/chart-shaping
functions, the route-aware parameters bar, and the Overview page skeleton
(stores, loading wrapper, mutually-exclusive chart/empty/error container,
metric-toggle panel) — every user story's chart-rendering behavior is built
on top of this. Includes two cross-cutting BDD scenarios (T006, T007) that
belong to no single user story but cover explicit spec MUST requirements.

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete.

- [X] T004 [P] Write failing unit tests for the HTTP client in `tests/unit/test_portfolio_analysis_client.py`, using `httpx.MockTransport` to cover: `list_accounts()` success, `list_attributes()` success, `get_timeseries()` success (repeated `attribute` query params, `start`/`end` as ISO dates), and error paths (`404`, `422`, timeout, connection error) per `contracts/portfolio-analysis-api.md`'s error table
- [X] T005 [P] Write failing unit tests for the pure helper functions in `tests/unit/test_overview_chart_shaping.py`, covering: last-completed-business-day computation (incl. a Monday-after-weekend case), earliest-`from_date` derivation from an account's nullable `capital_ledger`/`position_ladder` ranges, `entries` → Plotly trace shaping for one and multiple toggled metrics, the fixed metric→color mapping staying stable across calls, **and the fallback default color returned for an attribute name with no hardcoded palette entry** (per `contracts/portfolio-analysis-api.md`'s fallback-color note). **Implementation note**: importing `src/pages/overview.py` directly triggers `dash.register_page()` at module level, which errors without a prior `Dash(use_pages=True)` instantiation — unsafe for a plain unit-test import. The pure functions therefore live in a new side-effect-free `src/pages/_overview_chart.py` module (an alternative already anticipated by research.md #8), imported by both this test file and `overview.py` itself.
- [X] T006 [P] Write failing BDD scenarios in `tests/bdd/features/overview_empty_and_error_states.feature` + step definitions in `tests/bdd/steps/test_overview_steps.py` (stub the client via `httpx.MockTransport` to return zero `entries` / raise an error) covering spec.md's Edge Cases for FR-013 (a valid account/date/metric combination yields no data points → `overview-empty-state`, not a blank/broken chart) and FR-014 (accounts/attributes/timeseries call fails or the service is unavailable → `overview-error-state`, not a blank or indefinitely loading page) — `/speckit-analyze` finding C1
- [X] T007 [P] Write failing BDD scenario in `tests/bdd/features/shell_parameters_bar_unchanged.feature` + steps in `tests/bdd/steps/test_overview_steps.py` asserting that after this feature lands, the Positions/Performance/Income routes still render the unchanged 015 static, disabled `app-parameters-account`/`app-parameters-daterange` placeholder bar — `/speckit-analyze` finding C2
- [X] T008 [P] Define typed response models in `src/models/portfolio_analysis.py`: `AccountResourceRange`, `AccountSummary` (`account_name`, `capital_ledger: AccountResourceRange | None`, `position_ladder: AccountResourceRange | None`), `AttributeDefinition` (`name`, `description`, `source`), `TimeSeriesEntry` (`date` + dynamic attribute float fields), `TimeSeriesResponse` (per `data-model.md`) — satisfies the model-shape assertions in T004
- [X] T009 Implement `PortfolioAnalysisClient` (`Protocol`) and `HttpPortfolioAnalysisClient` in `src/services/portfolio_analysis_client.py`: `list_accounts() -> list[AccountSummary]`, `list_attributes() -> list[AttributeDefinition]`, `get_timeseries(account_name, attributes, start, end) -> TimeSeriesResponse`, using `httpx.Client(base_url=settings.portfolio_analysis_service_url, timeout=settings.request_timeout_seconds, transport=...)`, `structlog`-bound request/duration/error logging, and a typed exception raised on any `httpx.HTTPError` — mirrors `portfolio-analysis-service/app/clients/market_data_client.py`; makes T004 pass (depends on T008)
- [X] T010 Implement pure helper functions in `src/pages/_overview_chart.py` (see T005's implementation note for why this is a separate module from `overview.py`): `_last_business_day(today: date) -> date`, `_earliest_from_date(account: AccountSummary) -> date`, `_build_figure(entries, toggled_attributes) -> go.Figure` (one `go.Scatter` per toggled attribute, `layout.legend` positioned below the plot, per-point hovertemplate showing date/metric/GBP value, GBP-formatted y-axis), and the fixed attribute→color constant dict **with a defined fallback default color for any attribute name not in the dict** — makes T005 pass (depends on T008)
- [X] T011 Make the shared parameters bar route-aware in `src/layout/shell.py`: add a callback keyed on `dcc.Location.pathname` that renders real `app-parameters-account` (`dbc.Select`), `app-parameters-from-date`, `app-parameters-to-date` (`dcc.DatePickerSingle` ×2) when `pathname == "/"`, and leaves the existing 015 static disabled placeholder (`app-parameters-account`, `app-parameters-daterange`) unchanged on every other route (per `contracts/ui-contract.md` and research.md #7) — makes T007 pass. **Implementation note**: registered via `app.callback(...)` called from inside `build_shell(app, content)` (which now takes `app` as a parameter) rather than a bare module-level `@callback`, because `shell.py` is imported by `app.py` *before* `Dash()` is instantiated — a bare `@callback` at that point would hit the same "must be called after app instantiation" problem as `register_page`. `app.py` was updated to call `build_shell(app, content)` and to set `suppress_callback_exceptions=True` (required because `app-parameters-from-date`/`app-parameters-to-date` and the pattern-matched metric-toggle switches are dynamically created, not present in the initial static layout).
- [X] T012 Build the Overview page skeleton in `src/pages/overview.py`: `overview-accounts-store` / `overview-attributes-store` (`dcc.Store`), a metric-toggle panel with one `dbc.Tooltip` per option (`overview-attribute-tooltip-{name}`), and a mutually-exclusive container holding `overview-chart-loading` (`dcc.Loading` wrapping `overview-chart` / `dcc.Graph`), `overview-empty-state`, `overview-error-state`; add a shared `_render_timeseries(client, account_name, attributes, from_date, to_date) -> Div children` helper that calls `client.get_timeseries`, returns `overview-error-state` content on any client exception, `overview-empty-state` content on an empty `entries` list, else builds and returns the `overview-chart` Figure via `_build_figure` from T010 — makes T006 pass (depends on T009, T010). **Implementation note**: the toggle panel is a list of individually-`id`'d `dbc.Switch` + `dbc.Tooltip` pairs using Dash pattern-matching IDs (`{"type": "overview-attribute-toggle", "name": ...}`), not a single `dbc.Checklist` — `dbc.Checklist`'s per-option DOM ids aren't reliably targetable by an individual `dbc.Tooltip`, which `contracts/ui-contract.md`'s `overview-attribute-tooltip-{name}` per-option contract requires.
- [X] T013 Wire the Overview page-mount callback in `src/pages/overview.py`: fetch `client.list_accounts()` and `client.list_attributes()` into the two stores, populate `app-parameters-account`'s options (every account, per FR-001) and the metric-toggle panel's options + tooltips (every attribute, per FR-005/FR-006) (depends on T009, T011, T012). **Implementation note**: triggered by `Input("app-parameters-bar", "children")` (T011's own Output), not by `pathname` directly — this creates a genuine Dash callback-graph edge guaranteeing T011's callback resolves first, avoiding a race where this callback could try to populate `app-parameters-account` before shell.py has rendered the Overview variant of it.

**Checkpoint**: Foundation ready — `overview_empty_and_error_states.feature` and `shell_parameters_bar_unchanged.feature` pass; user story phases can now begin.

---

## Phase 3: User Story 1 - See account performance at a glance (Priority: P1) 🎯 MVP

**Goal**: Loading the Overview page immediately shows a populated
performance chart for the alphabetically-first account with `market_value`,
no selection required.

**Independent Test**: Load the Overview page and verify a line chart
renders with real data, a legend identifying the plotted line, and a hover
tooltip showing date/metric/value at any point.

### Tests for User Story 1 ⚠️

- [X] T014 [US1] Write failing BDD scenarios in `tests/bdd/features/overview_default_chart.feature` + step definitions in `tests/bdd/steps/test_overview_steps.py` (stub the client via `httpx.MockTransport`) covering spec.md's US1 Acceptance Scenarios 1–4: chart auto-renders with `market_value` for the alphabetically-first account with no user action; legend lists the plotted line with its color and metric name; hovering a point shows date/metric/value; the vertical axis shows GBP amounts

### Implementation for User Story 1

- [X] T015 [US1] Extend the page-mount callback in `src/pages/overview.py` (from T013) to auto-select the alphabetically-first `account_name` (FR-001a) and default the `market_value` metric toggle on, then derive `app-parameters-from-date.date` via `_earliest_from_date()` and `app-parameters-to-date.date` via `_last_business_day()` (T010) (depends on T013). **Implementation note**: split into two chained callbacks (`_apply_default_account` sets the account value + each switch's initial `value` prop at construction time; `_sync_date_range_to_selected_account` reacts to `app-parameters-account.value` changing — including this very first default-set — to derive the dates) rather than one combined callback, so the same date-derivation logic naturally also serves US2's account-switch case (T019) without duplicating it.
- [X] T016 [US1] Wire the initial chart render by calling `_render_timeseries()` (T012) with the T015 defaults as soon as they're set, outputting into the mutually-exclusive chart/empty/error container (depends on T015, T012). **Implementation note**: implemented as `_render_chart`, a single callback with Inputs on account/from-date/to-date/toggle-values — see T019/T022/T024's notes for why this one callback also covers those tasks (Dash forbids multiple callbacks targeting the same Output).
- [X] T017 [US1] Confirm/finish "bold, clear, professional" styling (FR-012) in `_build_figure()` (T010): chart title, gridlines, GBP-formatted axis ticks/hover values, font consistent with the `dbc.themes.BOOTSTRAP` theme already used by the shell (depends on T016)

**Checkpoint**: User Story 1 is fully functional and independently testable — run `pytest tests/bdd/features/overview_default_chart.feature` and the manual US1 walkthrough in `quickstart.md`.

---

## Phase 4: User Story 2 - Switch which account is being viewed (Priority: P2)

**Goal**: Selecting a different account updates the chart, date range, and
attribute options to that account's own data.

**Independent Test**: Select a different account and verify the chart
re-renders with that account's data, and the date range resets to that
account's own available history.

### Tests for User Story 2 ⚠️

- [X] T018 [US2] Write failing BDD scenarios in `tests/bdd/features/overview_switch_account.feature` + steps in `tests/bdd/steps/test_overview_steps.py` covering spec.md's US2 Acceptance Scenarios 1–3 (every account is listed in the Account control; selecting a different account updates the chart; the date range resets to the newly-selected account's own earliest date and the last completed business day) **and SC-006** (switching account patches the existing page in place — no full browser reload/navigation event fires) — `/speckit-analyze` finding G1

### Implementation for User Story 2

- [X] T019 [US2] Add an `app-parameters-account.value`-triggered callback in `src/pages/overview.py`: re-derive `from`/`to` dates from `overview-accounts-store` (no re-fetch of `/v1/accounts`, per research.md #9) using T010's helpers, then call `_render_timeseries()` (T012) with the new `account_name` + reset dates + currently-toggled metrics (depends on T012, T010, T013). **Implementation note**: this is `_sync_date_range_to_selected_account` (see T015's note — same callback serves both the initial default and every subsequent switch) plus `_render_chart` (T016) picking up the resulting date change as one of its Inputs.

**Checkpoint**: User Stories 1 and 2 both work independently — run both `.feature` files.

---

## Phase 5: User Story 3 - Narrow or widen the date range (Priority: P3)

**Goal**: Adjusting "from"/"to" focuses the chart on a specific period, with
invalid ranges prevented.

**Independent Test**: Change the "from" or "to" date to a narrower window
and verify the chart updates to show only that period; verify invalid dates
(to-after-today, from-after-to) are prevented.

### Tests for User Story 3 ⚠️

- [X] T020 [US3] Write failing BDD scenarios in `tests/bdd/features/overview_date_range.feature` + steps in `tests/bdd/steps/test_overview_steps.py` covering spec.md's US3 Acceptance Scenarios 1–2: a valid narrower from/to range re-renders the chart to that window; a "to" after today or a "from" after "to" is prevented without breaking the displayed chart

### Implementation for User Story 3

- [X] T021 [US3] Set `max_date_allowed=today` on `app-parameters-to-date` (static, set once in `shell.py` since "today" doesn't change mid-session) and a matching dynamic `max_date_allowed` on `app-parameters-from-date` synced to the *current* "to" value via a small callback (`_sync_from_date_max_to_to_date` in `src/pages/overview.py`) so FR-015 is enforced at the picker level (depends on T011)
- [X] T022 [US3] Add an `app-parameters-from-date.date`/`app-parameters-to-date.date`-triggered callback in `src/pages/overview.py`: on a valid change, call `_render_timeseries()` (T012) with the current account + new range + currently-toggled metrics (depends on T019, T021, T012). **Implementation note**: covered by `_render_chart` (T016's note) rather than a separate callback.

**Checkpoint**: User Stories 1–3 all work independently.

---

## Phase 6: User Story 4 - Choose which metrics to compare (Priority: P4)

**Goal**: Toggling metrics on/off updates the chart and legend accordingly,
with a tooltip explaining each metric; the toggle panel only appears on
Overview.

**Independent Test**: Toggle a metric off and verify its line/legend entry
disappears; toggle it back on and verify it reappears; hover a toggle and
verify its tooltip; navigate away and verify the toggle panel is gone.

### Tests for User Story 4 ⚠️

- [X] T023 [US4] Write failing BDD scenarios in `tests/bdd/features/overview_metric_toggles.feature` + steps in `tests/bdd/steps/test_overview_steps.py` covering spec.md's US4 Acceptance Scenarios 1–4: hovering a toggle shows its description tooltip; turning on a second metric adds a distinctly-colored line + legend entry; turning one off removes it while others remain; navigating to another nav section hides the toggle panel entirely

### Implementation for User Story 4

- [X] T024 [US4] Add a metric-toggle-triggered callback in `src/pages/overview.py`: if ≥1 metric selected, call `_render_timeseries()` (T012) with the updated attribute list; if 0 selected, render `overview-empty-state` directly without calling the client (FR-013 edge case) (depends on T022, T012). **Implementation note**: covered by `_render_chart` (T016's note), which takes the pattern-matched toggle switches' values as an `Input({"type": "overview-attribute-toggle", "name": ALL}, "value")`.
- [X] T025 [US4] Verify `overview-attribute-toggles` (the metric-toggle panel) and both `overview-*-store` elements are declared only inside `src/pages/overview.py`'s page layout (never in `src/layout/shell.py`), so Dash Pages naturally unmounts them on navigation away from Overview (FR-007) — fix placement if T012 introduced any shell-level leakage (depends on T012). **Verified**: confirmed by reading `src/pages/overview.py`'s `layout` — the toggle panel container and both `dcc.Store`s are declared there only; `src/layout/shell.py` contains neither.

**Checkpoint**: All four user stories are independently functional — full `tests/bdd` suite passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all stories.

- [X] T026 [P] Run `.venv/Scripts/python -m ruff check .` and `.venv/Scripts/python -m mypy .`; fix any issues in the new/modified files (`src/services/`, `src/models/`, `src/pages/overview.py`, `src/layout/shell.py`, `config/settings.py`) — both clean (`All checks passed!` / `Success: no issues found in 33 source files`)
- [ ] T027 [P] Run `.venv/Scripts/python -m pytest tests/unit tests/bdd` in full and confirm all pass. **Partially verified**: `tests/unit` — all 31 tests pass. `tests/bdd` — all 33 scenarios (22 new + 11 from 015) *collect* successfully (every Gherkin step resolves to a step definition, confirming no wiring/import errors across `app.py`/`shell.py`/`overview.py`); one was run and progressed correctly through app boot, stub installation, and Selenium/ChromeDriver startup, failing only at `SessionNotCreatedException: cannot find Chrome binary` — this sandbox has no Chrome/Chromium installed. **Not yet executed to a pass/fail verdict** — needs a machine with Chrome to actually run `pytest tests/bdd`.
- [ ] T028 Perform the full manual walkthrough in `quickstart.md` against a real running `portfolio-analysis-service` instance (all four user stories plus the non-Overview-page check). **Not done** — no running `portfolio-analysis-service` instance in this session; requires a manual pass by whoever has both services runnable locally.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational + US1's T012/T013 wiring (re-renders via the same helper); independently testable once its own phase is done
- **User Story 3 (Phase 5)**: Depends on Foundational + US2's T019 (date re-derivation groundwork) + T011's picker components
- **User Story 4 (Phase 6)**: Depends on Foundational + US3's T022 (extends the same render-triggering pattern)
- **Polish (Phase 7)**: Depends on all four user stories being complete

Stories are presented in priority order (P1→P4) because each phase's
callback extends the same `_render_timeseries()` call site added in T016 —
implementing them out of order is possible but re-introduces the same
integration point redundantly; sequential delivery is the natural path here.

### Within Each User Story

- Its `.feature` file(s) are written and confirmed failing before that
  story's implementation tasks (constitution Principle III)
- Implementation tasks within a story are ordered by their listed
  dependency, not parallelizable (they converge on the same
  `src/pages/overview.py` callback graph)

### Parallel Opportunities

- T001, T002, T003 (Setup) — different files, run together
- T004, T005, T006, T007 (Foundational tests) — different files, run together
- T008 (models) can run alongside T004–T007 — different file, no dependency
- T026, T027 (Polish) — independent checks, run together

Everything else in Phase 2 (T009–T013) and each user story's implementation
tasks converge on a small number of shared files (`overview.py`,
`shell.py`) and must be done in the listed order.

---

## Parallel Example: Foundational Phase

```bash
# Launch the independent Foundational tasks together:
Task: "Write failing unit tests for the HTTP client in tests/unit/test_portfolio_analysis_client.py"
Task: "Write failing unit tests for pure helper functions in tests/unit/test_overview_chart_shaping.py"
Task: "Write failing BDD scenarios for empty/error states in tests/bdd/features/overview_empty_and_error_states.feature"
Task: "Write failing BDD scenario for the unchanged non-Overview placeholder bar in tests/bdd/features/shell_parameters_bar_unchanged.feature"
Task: "Define typed response models in src/models/portfolio_analysis.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories; includes the empty/error-state and unchanged-placeholder-bar scenarios, T006/T007)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `overview_default_chart.feature` + the US1
   manual walkthrough in `quickstart.md`
5. Demo: Overview page shows a real, auto-populated chart

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. + User Story 1 → validate → MVP demo-able
3. + User Story 2 → validate → account switching works
4. + User Story 3 → validate → date-range narrowing works
5. + User Story 4 → validate → full spec scope complete

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] labels map each task to its spec.md user story for traceability
- T006, T007, and the fallback-color additions to T005/T010 were added by
  `/speckit-analyze` remediation (findings C1, C2, U1); G1's remediation
  (SC-006 no-full-reload) was folded into T018 rather than given its own
  task, per that finding's own recommendation. Finding A1 (FR-012's
  subjective wording) was accepted as-is with no task change, also per its
  own recommendation.
- Commit after each task or logical group (per repo convention — do not
  batch unrelated tasks into one commit)
- Stop at any checkpoint to manually validate that story's Independent Test
  before continuing
- No tasks were generated for the sample template's `tests/contract/`
  directory — this feature has no interface it exposes to others; its only
  contract is the one it *consumes* (`contracts/portfolio-analysis-api.md`),
  which T004 tests against
- **Cross-feature regression fix (015)**: `tests/bdd/features/application_shell.feature`'s
  "Content area occupies the remaining width with a parameters bar above it"
  scenario previously asserted on `#app-parameters-daterange` while sitting
  on the default (Overview) route. Since T011 makes Overview's parameters
  bar real (splitting that single placeholder input into
  `app-parameters-from-date`/`app-parameters-to-date`), that scenario was
  updated to first navigate to Positions — it was always testing generic
  shell chrome, not Overview-specific content, so this keeps it passing
  without weakening what it verifies.
- **Implementation-time consolidation**: tasks.md originally described
  separate "add a callback" tasks for T019/T022/T024 (account-change,
  date-change, toggle-change). Dash does not allow two callbacks to target
  the same `Output`, so all three — plus T016's initial render — are
  implemented as one callback (`_render_chart`) with four `Input`s. This is
  noted individually on each affected task above; functionally nothing
  described in spec.md changed, only how many Python functions implement it.
