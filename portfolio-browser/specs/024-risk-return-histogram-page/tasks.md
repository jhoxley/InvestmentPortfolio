---
description: "Task list for Risk Page (Return Histogram)"
---

# Tasks: Risk Page (Return Histogram)

**Input**: Design documents from `specs/024-risk-return-histogram-page/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED — the constitution's Principle III (Test-First BDD) is
non-negotiable. Every test task must be run and seen **failing** before its implementation task.

**Organization**: Grouped by user story (P1–P3 from spec.md). All paths are relative to
`portfolio-browser/`.

**Deviation from plan.md's file layout**: none — `risk.py`/`_risk_chart.py`/`_risk_table.py` follow
the exact `performance.py`/`_performance_chart.py` split already used, with one extra pure-function
module (`_risk_table.py`) since this page renders two outputs instead of one.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3

---

## Phase 1: Setup

- [X] T001 Add a `risk` entry (`key: risk`, `label: Risk`, `order: 5`) to `nav_sections` in
  `config/content.yaml`, after the existing `projection` entry.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The response models and outbound client call every user story's render path depends
on. Nothing here is wired to a page, so no user-visible behaviour exists yet.

- [X] T002 [P] Write failing unit tests in `tests/unit/test_portfolio_analysis_models.py` (new
  file, or append if it already covers other models) asserting `ReturnHistogramResponse.model_validate(...)`
  correctly parses the OpenAPI example payload from
  `portfolio-analysis-service/specs/011-risk-return-histogram/contracts/openapi.yaml`
  (`account_name: HL-SIPP`, `histogram: [[-25,1],[-3,4],[0,12],[7,9],[65,1]]`, full `statistics`
  block including `std_dev_bands`), and a second payload where `mean`/`median`/`mode`/`minimum`/
  `maximum`/`std_dev`/`skewness`/`kurtosis` are all `null` (count-0 case) validates with those
  fields as `None` and `std_dev_bands: []`. Run and confirm they fail (models don't exist yet).
- [X] T003 [US layer: none — shared] Add `StdDevBand`, `HistogramStatistics`, and
  `ReturnHistogramResponse` Pydantic models to `src/models/portfolio_analysis.py`, field-for-field
  matching `portfolio-analysis-service/app/models/risk.py` (per data-model.md): `histogram` typed
  `list[tuple[int, int]]`; `links: dict[str, str] = Field(default_factory=dict)` matching the
  existing `links` field convention on `TimeSeriesResponse`/`PositionsResponse`. Confirm T002 passes.
- [X] T004 [P] Write a failing unit test in `tests/unit/test_portfolio_analysis_client.py` —
  `test_get_return_histogram_success` — using `httpx.MockTransport` (mirroring
  `test_list_accounts_success`'s pattern in the same file): asserts the request path is
  `/v1/accounts/{account_name}/risk/return-histogram`, `start`/`end` query params are sent as
  ISO date strings, and the parsed `ReturnHistogramResponse` matches a stubbed JSON response. Add a
  second test, `test_get_return_histogram_failure_raises`, asserting a non-2xx response raises
  `PortfolioAnalysisServiceError` (mirroring the existing error-path test for `get_performance`).
  Run and confirm both fail (method doesn't exist yet).
- [X] T005 Add `get_return_histogram(self, account_name: str, start: date, end: date) ->
  ReturnHistogramResponse` to both the `PortfolioAnalysisClient` Protocol and
  `HttpPortfolioAnalysisClient` in `src/services/portfolio_analysis_client.py`, following the
  exact `_get(...)` + `.model_validate(...)` shape `get_performance` already uses (no
  `periodicity` param — this endpoint has none). Confirm T004 passes.

**Checkpoint**: Models and client call are ready; no page references them yet.

---

## Phase 3: User Story 1 — See the Return Distribution for an Account (Priority: P1) 🎯 MVP

**Goal**: Opening `/risk` shows a pre-selected account, a default full-history date range, a bar
chart of basis-point buckets vs. day-counts, and a statistics table (count, mean, median, mode,
minimum, maximum, std_dev, skewness, kurtosis — no `std_dev_bands`) in a single 60/40 row.

**Independent Test**: Open the Risk page for an account with recorded return history; verify the
bar chart and the 9-row statistics table both render without any further interaction.

### Tests for User Story 1 (write first; must fail)

- [X] T006 [P] [US1] Write failing unit tests in `tests/unit/test_risk_chart.py` for a pure
  `build_figure(histogram: list[tuple[int, int]]) -> go.Figure` in `src/pages/_risk_chart.py`:
  bar `x` values equal each pair's first element in the given order, bar `y` values equal each
  pair's second element, and an empty list produces a `Figure` with an empty trace (no exception).
- [X] T007 [P] [US1] Write failing unit tests in `tests/unit/test_risk_table.py` for a pure
  `build_rows(statistics: HistogramStatistics) -> list[dict[str, str]]` in
  `src/pages/_risk_table.py`: returns exactly 9 rows in the order count, mean, median, mode,
  minimum, maximum, std_dev, skewness, kurtosis; no row for `std_dev_bands`; a statistics object
  with `mean=None` (etc.) renders that row's `"value"` as the literal string `"N/A"`; a populated
  numeric value renders as its `str()` (or a documented format — assert whatever format the
  implementation task picks, then keep the implementation consistent).
- [X] T008 [US1] Create `tests/bdd/features/risk_view_histogram.feature` with the three scenarios
  from spec.md User Story 1 (page reachable from navigation; opening the page shows a histogram and
  a statistics table with the 9 named rows and no `std_dev_bands`; chart and table sit in one row,
  chart ~60% / table ~40% width), in the project's existing step vocabulary style (see
  `tests/bdd/features/performance_default_view.feature` for the idiom).
- [X] T009 [US1] Add `tests/bdd/steps/test_risk_steps.py` registering
  `scenarios("../features/risk_view_histogram.feature")`, with a `_FakeClient`
  (`list_accounts` + `get_return_histogram`) monkeypatched onto `src.pages.risk._get_client`,
  mirroring `tests/bdd/steps/test_performance_steps.py`'s `_FakeClient` pattern. Add step
  definitions for: the "Risk" nav entry existing and navigating to it; asserting the chart's bar
  count/x-values match the fake histogram; asserting the table's row labels/values via Selenium
  reading `#risk-statistics-table`'s rendered rows; asserting the two `dbc.Col` widths (7 and 5) via
  their rendered class names or computed widths. Run the feature and confirm every scenario fails
  (page/route doesn't exist yet). **NOT VERIFIED: no Chrome/chromedriver on this machine, so BDD
  scenarios are collected (all 15 step bindings resolve with no missing-step errors) but SKIPPED;
  red/green was not observed. Run on a machine with Chrome.**

### Implementation for User Story 1

- [X] T010 [P] [US1] Create `src/pages/_risk_chart.py` implementing `build_figure` (T006 passes):
  one `go.Bar` trace, `x`/`y` from the histogram pairs, `plotly_white` template, axis titles
  "Return (bps)" / "Days", mirroring `_performance_chart.py`'s styling conventions (font, margins,
  gridlines) but with a bar chart instead of line traces.
- [X] T011 [P] [US1] Create `src/pages/_risk_table.py` implementing `build_rows` (T007 passes):
  iterate `HistogramStatistics.model_dump()` in declared field order, skip `std_dev_bands`, map
  each remaining key to a human label (`"count"→"Count"`, `"std_dev"→"Std Dev"`, etc.), and render
  `None` as `"N/A"`.
- [X] T012 [US1] In `src/layout/shell.py`: add `_RISK_PATH = "/risk"`, a
  `_build_risk_parameters_bar()` returning
  `build_account_date_controls(first_shortcut_label="10Y")` (label only at this point — the click
  mapping to `SHORTCUT_10Y` is US2's concern), and a branch in `_render_parameters_bar` for
  `_RISK_PATH`. Update the module docstring's route list.
- [X] T013 [US1] Create `src/pages/risk.py` mirroring `performance.py`'s structure:
  `dash.register_page(__name__, path="/risk", name="Risk")`; `_get_client()` factory (identical
  pattern); `_empty_state`/`_error_state` helpers with `risk-` prefixed ids; layout with
  `dcc.Interval(id="risk-mount-trigger", ...)`, `dcc.Store(id="risk-accounts-store")`, and a
  `dbc.Row` of two `dbc.Col`s (`width=7` wrapping `dcc.Loading(html.Div(id="risk-chart-container"))`,
  `width=5` wrapping `dcc.Loading(html.Div(id="risk-table-container"))`) per contracts/ui-contract.md.
- [X] T014 [US1] In `src/pages/risk.py` add `_fetch_accounts` (mirrors
  `performance.py::_fetch_accounts_and_attributes` minus the attributes fetch): populates
  `risk-accounts-store` and `app-parameters-account.options`; on failure sets both containers to
  the shared error state.
- [X] T015 [US1] In `src/pages/risk.py` add `_apply_default_account` and
  `_sync_date_range_to_selected_account` (both copied near-verbatim from `performance.py`, using
  `_earliest_from_date`/`_last_business_day` for the same "full recorded history" default), and
  `_sync_from_date_max_to_to_date` (identical to every other page's copy).
- [X] T016 [US1] In `src/pages/risk.py` add `_render_histogram_and_table`: Inputs = account value,
  from-date, to-date; calls `client.get_return_histogram(...)`; on
  `PortfolioAnalysisServiceError` sets both containers to the shared error state; on
  `statistics.count == 0` sets both containers to the shared empty state (no chart, no table,
  per spec Edge Cases); otherwise sets `risk-chart-container` to a
  `dcc.Graph(figure=_risk_chart.build_figure(response.histogram))` and `risk-table-container` to a
  `dash_table.DataTable` built from `_risk_table.build_rows(response.statistics)` with columns
  headed exactly `"statistic"` and `"value"`.
- [X] T017 [US1] Run
  `python -m pytest tests/unit/test_risk_chart.py tests/unit/test_risk_table.py tests/unit/test_portfolio_analysis_models.py tests/unit/test_portfolio_analysis_client.py tests/bdd -k risk`;
  confirm T002, T004, T006, T007 pass and T008/T009's scenarios pass (or are skipped with a
  recorded reason if no Chrome/chromedriver is available in this environment — do not report BDD
  as passing without having actually run it).

**Checkpoint**: US1 is a shippable MVP — visiting `/risk` shows a real chart and table for a real
account and default range.

---

## Phase 4: User Story 2 — Quickly Change the Observation Window with Preset Buttons (Priority: P2)

**Goal**: The five shortcut buttons (10Y/1Y/3Y/5Y/All) each resolve the from-date correctly,
clamped to the account's earliest recorded date, and refresh the chart/table.

**Independent Test**: Click each of "10Y", "1Y", "3Y", "5Y", "All" in turn for an account with
over ten years of history; verify the from-date and the rendered chart/table update each time.

### Tests for User Story 2 (write first; must fail)

- [X] T018 [P] [US2] Write a failing unit test in `tests/unit/test_date_range_controls.py` (extend
  if it exists, else create it) asserting `_shortcut_from_date(SHORTCUT_10Y, account, today)`
  returns `today` minus 10 years, clamped to the account's earliest recorded date when the
  unclamped result would be earlier — mirroring the existing 1Y/3Y/5Y assertions in that module's
  own test suite style.
- [X] T019 [US2] Create `tests/bdd/features/risk_shortcut_buttons.feature` with the two scenarios
  from spec.md User Story 2 (each preset button resolves to the matching trailing window and
  refreshes the view; a preset window with too little history clamps to the earliest date without
  error).
- [X] T020 [US2] Add step definitions to `tests/bdd/steps/test_risk_steps.py` for clicking each
  shortcut button by its shared DOM id and asserting the resulting `app-parameters-from-date`
  value and the refreshed chart/table content, mirroring
  `tests/bdd/steps/test_performance_steps.py`'s shortcut-button steps. Run and confirm failure
  (shortcut mapping not wired to `SHORTCUT_10Y` yet). **NOT VERIFIED: no Chrome/chromedriver on
  this machine, so BDD scenarios are collected (all bindings resolve) but SKIPPED; red/green was
  not observed. Run on a machine with Chrome.**

### Implementation for User Story 2

- [X] T021 [US2] Add `SHORTCUT_10Y = "10y"` and a `SHORTCUT_10Y: 10` entry to
  `_SHORTCUT_YEAR_OFFSETS` in `src/components/date_range_controls.py` (additive only — do not
  change `SHORTCUT_YTD`/`SHORTCUT_1Y`/`SHORTCUT_3Y`/`SHORTCUT_5Y`/`SHORTCUT_ALL` or
  `_build_shortcut_buttons`'s five-slot layout). Confirm T018 passes.
- [X] T022 [US2] In `src/pages/risk.py` add `_SHORTCUT_CODE_BY_BUTTON_ID` mapping
  `"overview-shortcut-ytd"` (the shared first-button DOM id, labelled "10Y" via T012) to
  `SHORTCUT_10Y`, and the other four shared button ids to their existing
  `SHORTCUT_1Y`/`SHORTCUT_3Y`/`SHORTCUT_5Y`/`SHORTCUT_ALL` codes — the same page-local remapping
  `performance.py` already uses for its "ITD"→`SHORTCUT_ALL` mapping. Add
  `_apply_date_range_shortcut` (copied from `performance.py`, using this page's own mapping) and
  the `_PAGE_SCOPE_INPUT`/`_REFRESH_DISABLED_IDS` scaffolding it depends on (same pattern as
  `performance.py`'s own module-level constants).
- [X] T023 [US2] Add `running=[...]` to `_render_histogram_and_table` (T016) disabling
  `_REFRESH_DISABLED_IDS` during the fetch, matching every other page's refresh-disable behaviour.
- [X] T024 [US2] Run
  `python -m pytest tests/unit/test_date_range_controls.py tests/bdd -k risk`; confirm T018–T020
  pass, and that `tests/unit/test_callback_registration.py` reports no collisions introduced by
  `risk.py`'s new callbacks.

**Checkpoint**: US1 and US2 both independently verified.

---

## Phase 5: User Story 3 — Fine-Tune the Exact Date Range (Priority: P3)

**Goal**: Manually editing either date picker refreshes the view to exactly that range,
independent of the preset buttons; switching accounts resets the range to the new account's
default.

**Independent Test**: Set a custom start/end range narrower than any preset; verify the chart and
table refresh to exactly that range. Switch accounts; verify the range resets to the new account's
default.

### Tests for User Story 3 (write first; must fail)

- [X] T025 [US3] Create `tests/bdd/features/risk_manual_date_range.feature` with the two scenarios
  from spec.md User Story 3 (manually editing either date refreshes the view; switching accounts
  resets the range to that account's own default).
- [X] T026 [US3] Add step definitions to `tests/bdd/steps/test_risk_steps.py` for directly setting
  the From/To `DatePickerSingle` values (mirroring how `tests/bdd/steps/test_performance_steps.py`
  or `test_overview_steps.py` already drive those pickers) and for switching the account dropdown
  mid-session, asserting the chart/table content and the reset date-range values. Run and confirm
  failure only if a real gap exists — `_render_histogram_and_table`'s Inputs (T016) and
  `_sync_date_range_to_selected_account` (T015) already cover this path, so this may instead
  surface as a passing "no gap found" run; if so, still keep the feature file as regression
  coverage per Principle III. **NOT VERIFIED: no Chrome/chromedriver on this machine, so BDD
  scenarios are collected (all bindings resolve) but SKIPPED; red/green was not observed. Run on a
  machine with Chrome.**
- [X] T027 [US3] Add a unit test to `tests/unit/test_risk_table.py` or a new
  `tests/unit/test_risk_page.py` for the end-date-not-after-start-date validation message path
  (mirror whichever existing page's validation-message test this project already has, e.g.
  Projection's `projection-date-validation` pattern) — confirm the same shared validation
  treatment applies here, or add it if the shared `date_range_controls.py` doesn't already cover
  it end-to-end for a plain from/to range (it currently only clamps `max_date_allowed`, so add
  whatever inline message component + callback `risk.py` needs, following FR-007).

### Implementation for User Story 3

- [X] T028 [US3] If T026/T027 exposed a gap (e.g. no inline validation message when To ≤ From),
  add a `dbc.FormText(id="risk-date-validation", color="danger")` to the Risk parameters bar
  (`shell.py::_build_risk_parameters_bar`) and a callback in `risk.py` populating it, mirroring
  Projection's `projection-date-validation` pattern. If no gap was found, record "no gaps found —
  existing from/to Inputs already satisfy FR-006/FR-007/FR-008" in the T026 commit message instead
  of making a change.
- [ ] T029 [US3] Run `python -m pytest tests/bdd -k risk` for the full Risk BDD suite (all three
  feature files) and confirm every scenario passes.

**Checkpoint**: All three user stories independently verified.

---

## Phase 6: Polish & Cross-Cutting

- [X] T030 [P] Run `ruff check .` and `mypy .` from `portfolio-browser/`; fix any findings in
  files touched by this feature.
- [X] T031 [P] Update `README.md` (or wherever the page list is described, if anywhere) to mention
  the new Risk page; skip if no such page-list description exists. **Skipped: no `README.md` or
  other page-list description exists in `portfolio-browser/`.**
- [ ] T032 Follow `specs/024-risk-return-histogram-page/quickstart.md` manually against a running
  `portfolio-analysis-service` that includes the `/risk/return-histogram` endpoint; confirm every
  step and record the result in the PR description. If the endpoint is unavailable, say so
  explicitly rather than reporting this as done. **NOT VERIFIED: no running
  portfolio-analysis-service instance in this environment. Run manually before merging.**

---

## Dependencies & execution order

- Phase 1 (T001) has no dependencies; can run any time before T012.
- Phase 2 (T002–T005) blocks every user story: T002→T003 sequential; T004→T005 sequential; T003
  and T004/T005 can run in parallel (different files).
- US1 needs Phase 2 complete. T006, T007, T008 can start in parallel; T009 depends on T008 (same
  feature file). T010 depends on T006; T011 depends on T007; T012 depends on T001 (parameters bar
  needs the nav route to matter, though it can technically be written earlier — kept here for
  clarity); T013 depends on T012; T014–T016 depend on T013 and on T010/T011 for the render task;
  T017 last.
- US2 needs US1 complete (it exercises the wired page and its shared shortcut buttons). T018
  parallel with T019; T020 depends on T019; T021 depends on T018; T022 depends on T020 and T021;
  T023 depends on T022; T024 last.
- US3 needs US1 (and benefits from US2 being done, though it does not depend on it). T025→T026;
  T027 parallel with T026; T028 depends on T026/T027's findings; T029 last.
- Polish after US3.

### Parallel examples

```text
Phase 2:   T003 + (T004→T005)          (models file vs client file)
US1 tests: T006 + T007 + T008          (three different files)
US1 impl:  T010 + T011                 (chart helper vs table helper)
US2 tests: T018 + T019
Polish:    T030 + T031
```

## Implementation strategy

1. **MVP = Phase 1 + Phase 2 + US1** (T001–T017): the page exists, is reachable, and shows a real
   chart and table for the default account/range. Stop and demo here if needed.
2. **US2** adds the five preset shortcut buttons, including the new "10Y" option.
3. **US3** adds/confirms manual date-range editing and the account-switch reset.
4. **Polish** then manual verification against the real service.

## Task summary

- Total: 32 tasks — Setup 1, Foundational 4, US1 12 (T006–T017), US2 7 (T018–T024), US3 5
  (T025–T029), Polish 3.
- Test tasks (written first): T002, T004, T006, T007, T008–T009, T018–T020, T025–T027.
