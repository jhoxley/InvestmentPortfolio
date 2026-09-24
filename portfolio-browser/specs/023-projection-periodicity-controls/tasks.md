---
description: "Task list for Periodicity Control for the Projection Page"
---

# Tasks: Periodicity Control for the Projection Page

**Input**: Design documents from `specs/023-projection-periodicity-controls/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED — the constitution's Principle III (Test-First BDD) is
non-negotiable. Every test task must be run and seen **failing** before its implementation task.

**Organization**: Grouped by user story (P1–P2 from spec.md). All paths are relative to
`portfolio-browser/`.

**Ordering note (deviation from a strict "US2 owns derivation" split)**: today's page already
derives an interval inline on every render. To keep FR-010 (defaults unchanged) true the moment the
store replaces that inline call, the derive callback ships in **US1**, not US2. US2 then *proves and
hardens* the default/explicit rules with its own scenarios and unit tests.

**Deviation from plan.md's file layout**: `src/pages/projection.py` cannot be imported in a plain
unit test (its `dash.register_page` needs a live Dash app), so the pure store-transition logic goes
in a new underscore-prefixed helper module `src/pages/_projection_periodicity.py` (same pattern as
the existing `_projection_chart.py`). The Dash callbacks in `projection.py` stay thin wrappers.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 or US2

---

## Phase 1: Setup

**No tasks required.** No new dependency, config key, marker or environment setting. The existing
`periodicity` config block, the shared component and `get_projection(..., periodicity=)` are reused.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Pure, unit-testable logic and test doubles that both stories need. Nothing here is
wired to the page, so user-visible behaviour is unchanged.

- [X] T001 [P] Write failing unit tests in `tests/unit/test_projection_periodicity.py` for a pure function `next_periodicity_state(store_data, accounts_data, account_name, target_date, config)`: (a) empty store + account earliest 2016-04-20 + target 2027-04-20 (≈11y) → `{"value": "annual", "explicit": False}`; (b) each boundary — span exactly 1y → `day`, exactly 3y → `month`, exactly 5y → `quarter`, 5y+1 day → `annual`; (c) store `{"value": "month", "explicit": True}` → returned **unchanged** whatever the span; (d) account not found or account has no `position_ladder` → `{"value": None, "explicit": False}` (unless explicit, then unchanged); (e) never returns `week` for spans of 1 day to 40 years; (f) never returns `explicit: True` when the input was not explicit. Run and confirm they fail (module does not exist).
- [X] T002 Create `src/pages/_projection_periodicity.py` implementing `next_periodicity_state` to satisfy T001 by reusing `derive_periodicity` from `src/components/periodicity_controls.py` and `PeriodicityConfig.value_for_key` from `config/content.py`; span = account `position_ladder.from_date` → target date (research.md #3). Add type hints and a docstring; no Dash imports. Confirm T001 passes.
- [X] T003 [P] Extend `_FakeProjectionClient` in `tests/bdd/steps/test_projection_steps.py` to record every `get_projection` call as `self.calls: list[dict]` (account, projection_date, returns, start, periodicity), and make its entries honour `periodicity`: for `quarter`/`month`/`annual`/`week` return one historical and one projected point per calendar period (date = period start) between the span bounds; `None`/`day` keeps today's two-point output so existing scenarios are unaffected. Run the existing three projection feature files and confirm they still pass. **NOT VERIFIED: no Chrome/chromedriver on this machine, so BDD scenarios are collected but SKIPPED; red/green was not observed. Run on a machine with Chrome.**

**Checkpoint**: helper + fake ready; app behaviour unchanged.

---

## Phase 3: User Story 1 — Choose how densely the projection is plotted (P1) 🎯 MVP

**Goal**: A Periodicity control on Projection that redraws historical and projected lines at the
chosen interval, with one chart fetch per action, disabled during refresh, defaults unchanged.

**Independent Test**: Load Projection, click "20Y", click "month" → chart redraws monthly, account,
start date, target date and toggles unchanged, "month" highlighted.

### Tests for User Story 1 (write first; must fail)

- [X] T004 [US1] Create `tests/bdd/features/projection_periodicity.feature` with the four scenarios from spec User Story 1 (control present with five options in order; selecting an interval redraws historical + projected series; "day" plots one point per business day; control disabled while refreshing), rewritten in the project's step vocabulary (e.g. `Given portfolio-analysis-service has multiple accounts with recorded market-value history`, `And the Projection page has finished loading its default chart`).
- [X] T005 [US1] Add step definitions to `tests/bdd/steps/test_projection_steps.py` and register the feature via `scenarios("../features/projection_periodicity.feature")`: `a control labelled "Periodicity" is shown in the parameters bar`, `its options are exactly ... in that order` (read the `projection-parameters-periodicity-*` button texts), `the user selects periodicity "{label}" on Projection` (click `#projection-parameters-periodicity-{key}`), assertions on the plotted points per series using `_chart_trace_names_and_dates`, an assertion that the last `stub_client.calls[-1]["periodicity"]` equals the mapped service value, and a disabled-while-refreshing check (make the fake sleep briefly on a flag set by a Given step, then assert `disabled` on the buttons). Run the feature and confirm every scenario fails. **NOT VERIFIED: no Chrome/chromedriver on this machine, so BDD scenarios are collected but SKIPPED; red/green was not observed. Run on a machine with Chrome.**
- [X] T006 [P] [US1] Add to `tests/unit/test_projection_periodicity.py` a failing test that `explicit_state_for_click("month", config)` returns `{"value": "month", "explicit": True}` and `"year"` returns `{"value": "annual", "explicit": True}`, and that an unknown key raises `KeyError`.

### Implementation for User Story 1

- [X] T007 [US1] Add `explicit_state_for_click(option_key, config)` to `src/pages/_projection_periodicity.py` (T006 passes).
- [X] T008 [US1] In `src/layout/shell.py::_build_projection_parameters_bar`, splice `*build_periodicity_control("projection", get_content_config().periodicity)` into the returned list after the "Project to" calendar column and before the validation-message column; update the docstring.
- [X] T009 [US1] In `src/pages/projection.py`: add module-level `_PERIODICITY_CONFIG = get_content_config().periodicity`, `_PERIODICITY_STORE_ID = periodicity_store_id("projection")`, `_PERIODICITY_BUTTON_IDS` (built with `periodicity_component_id`), and add `dcc.Store(id=_PERIODICITY_STORE_ID, data=None)` to `layout`. Import the helpers from `src/components/periodicity_controls.py` (export `periodicity_store_id` from its `__all__` if needed).
- [X] T010 [US1] In `src/pages/projection.py` add `_apply_periodicity_click` (Inputs: the five buttons' `n_clicks` and `_PAGE_SCOPE_INPUT`.`max_intervals`; Output: store `data`, `allow_duplicate=True`; `prevent_initial_call=True`; `PreventUpdate` unless `ctx.triggered_id` is a button id; writes `explicit_state_for_click(...)`), per contracts/ui-contract.md #1.
- [X] T011 [US1] In `src/pages/projection.py` add `_derive_periodicity` (Inputs: `projection-target-store`.`data`, `app-parameters-account`.`value`, `projection-accounts-store`.`data`, `_PAGE_SCOPE_INPUT`.`max_intervals`; State: store `data`; Output: store `data`, `allow_duplicate=True`; `prevent_initial_call=True`). `PreventUpdate` when there is no account, accounts data or target; otherwise return `next_periodicity_state(...)`. Per contracts/ui-contract.md #2 it must always write (so the chart fires once) and must never set `explicit: True`.
- [X] T012 [US1] In `src/pages/projection.py` add `_style_periodicity_buttons` (Input: store `data`; Outputs: `active` and `outline` of each button, in config order) using `periodicity_button_states`, mirroring `overview.py::_style_periodicity_buttons`.
- [X] T013 [US1] Change `_render_chart` in `src/pages/projection.py`: Inputs become account, start date, `Input(store, "data")`, return toggles; `State("projection-target-store", "data")` replaces the target Input; keep the accounts store State; add `running=[(Output(button_id, "disabled"), True, False) for button_id in _PERIODICITY_BUTTON_IDS]`. Pass `periodicity=store["value"] if store else None`. Remove the inline `_derive_projection_periodicity` call and delete that now-unused function. Keep every empty/error state message unchanged.
- [X] T014 [US1] Update the module docstring in `src/pages/projection.py` (callback list items 8–11; drop "this page has no visible periodicity control of its own"). Ensure `PortfolioAnalysisClient.get_projection` signature in `src/services/portfolio_analysis_client.py` is unchanged (no edit expected).
- [ ] T015 [US1] Run `python -m pytest tests/unit tests/bdd -k "projection or callback_registration"`; confirm T004–T006 pass, all existing projection scenarios pass (the target moved from Input to State), and `test_callback_registration.py` reports no collisions. **Partial: unit + callback-registration tests pass (214); BDD skipped (no Chrome). Left unchecked until the BDD suite has run.**

**Checkpoint**: US1 is a shippable MVP — visible, working control with today's defaults preserved.

---

## Phase 4: User Story 2 — Sensible default interval, shown in the control (P2)

**Goal**: Prove and harden the default rules: derived interval from the plotted span using the
shared thresholds, shown in the control, never "week", overridden only by an explicit click, and
sticky across horizon clicks, calendar picks and account switches.

**Independent Test**: With no click, choose targets giving spans of ~6 months, 2, 4 and 10 years →
control and service call show day, month, quarter, year; click "month", then "20Y" → still month.

### Tests for User Story 2 (write first; expected to expose gaps, not necessarily fail)

- [X] T016 [US2] Create `tests/bdd/features/projection_periodicity_defaults.feature` with the spec's User Story 2 scenarios: Scenario Outline on span → interval (using accounts with configurable earliest date so spans of 6 months, 1, 2, 3, 4, 5 and 10 years are reachable), horizon click derives coarser interval, "week" never automatic, explicit choice not overridden by a horizon click, explicit choice survives an account switch.
- [X] T017 [US2] Add steps to `tests/bdd/steps/test_projection_steps.py` and register the feature: a Given that installs an account whose earliest record produces a requested span to the chosen target (extend `_ACCOUNTS`-style helper), `the user has not chosen a periodicity`, `the Periodicity control shows "{label}" as the interval in effect` (assert the button with `active` class), `the chart is plotted at "{label}"` (assert last `stub_client.calls[-1]["periodicity"]`), `the user explicitly selects periodicity "{label}"`, `the user switches to account "{name}"`. Run and record any failures; fix the implementation (not the test) if a rule from FR-005–FR-009 is violated. **NOT VERIFIED: no Chrome/chromedriver on this machine, so BDD scenarios are collected but SKIPPED; red/green was not observed. Run on a machine with Chrome.**
- [X] T018 [P] [US2] Add unit tests to `tests/unit/test_projection_periodicity.py` for the transition table in data-model.md: derive → explicit click → derive again leaves the state unchanged; an account switch that changes the earliest date does not alter an explicit state; a derived state followed by a different span produces the new derived value with `explicit: False`.
- [X] T019 [US2] Add a guard to `tests/unit/test_projection_periodicity.py` (or extend `tests/unit/test_content_config.py`) asserting the Projection button ids generated for `"projection"` differ from the Overview/Positions ids and that every configured option key has a button id, so a config change cannot silently drop a Projection button.

### Implementation for User Story 2

- [X] T020 [US2] Fix any gap found by T017/T018 in `src/pages/_projection_periodicity.py` or the callbacks in `src/pages/projection.py`. If nothing failed, record "no gaps found" in the T017 commit message rather than making a change. **NOT VERIFIED: no Chrome/chromedriver on this machine, so BDD scenarios are collected but SKIPPED; red/green was not observed. Run on a machine with Chrome.**
- [ ] T021 [US2] Run `python -m pytest tests/unit tests/bdd -k "projection or callback_registration or periodicity"` and confirm Overview and Positions periodicity scenarios (`overview_periodicity*.feature`, `positions_periodicity.feature`) still pass. **Partial: unit + callback-registration tests pass (214); BDD skipped (no Chrome). Left unchecked until the BDD suite has run.**

**Checkpoint**: both stories independently verified.

---

## Phase 5: Polish & cross-cutting

- [X] T022 [P] Run `ruff check .` and `mypy .` from `portfolio-browser/`; fix any findings in files touched by this feature.
- [X] T023 [P] Update `README.md` (or the relevant page docs, if the Projection page is described) to mention the Periodicity control; skip if no Projection description exists.
- [ ] T024 Follow `specs/023-projection-periodicity-controls/quickstart.md` manually against a running `portfolio-analysis-service` that includes the projection endpoint; confirm steps 1–5 and record the result in the PR description. If the endpoint is unavailable, say so explicitly rather than reporting this as done.

---

## Dependencies & execution order

- Phase 2 (T001–T003) blocks both stories. T001→T002 sequential; T003 parallel with both.
- US1: T004→T005 (tests, same feature/steps); T006 parallel with T004; T007 after T006; T008, T009 parallel (different files); T010–T012 after T009 and T007 (same file, sequential); T013 after T010–T012; T014→T015 last.
- US2 needs US1 complete (it exercises the wired page). T016→T017; T018, T019 parallel with them; T020 after T017/T018; T021 last.
- Polish after US2.

### Parallel examples

```text
Phase 2:   T001 + T003            (different files)
US1 tests: T004 + T006            (feature file vs unit test file)
US1 impl:  T008 + T009            (shell.py vs projection.py)
US2 tests: T016 + T018 + T019
Polish:    T022 + T023
```

## Implementation strategy

1. **MVP = Phase 2 + US1** (T001–T015): the control works and defaults are unchanged. Stop and
   demo here if needed.
2. **US2** adds proof and hardening of the default/explicit rules; it may need no production change.
3. **Polish** then manual verification against the real service.

## Task summary

- Total: 24 tasks — Foundational 3, US1 12 (T004–T015), US2 6 (T016–T021), Polish 3.
- Test tasks (written first): T001, T004–T006, T016–T019.
