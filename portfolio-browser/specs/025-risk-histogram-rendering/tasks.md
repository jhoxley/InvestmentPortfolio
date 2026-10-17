---
description: "Task list for Readable Return Histogram Rendering"
---

# Tasks: Readable Return Histogram Rendering

**Input**: Design documents from `specs/025-risk-histogram-rendering/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Included and REQUIRED — the constitution's Principle III (Test-First BDD) is
non-negotiable. Every test task must be run and seen **failing** before its implementation task.

**Organization**: Grouped by user story (P1–P3 from spec.md). All paths are relative to
`portfolio-browser/`.

**Deviation from plan.md's file layout**: none — this feature rewrites the existing
`src/pages/_risk_chart.py` module and its one call site in `risk.py`; no new files beyond test
files.

**Ordering note**: `build_figure`'s signature change (`histogram` → `histogram, statistics`) is
shared by every user story's bars, so it ships in Foundational rather than being deferred to US1,
to avoid US2/US3 each needing to re-touch the same function signature.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3

---

## Phase 1: Setup

**No tasks required.** No new dependency, config key, or environment setting — Plotly's
`add_vline` is already available in the pinned `plotly>=5` requirement.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The bucketing pass and the `build_figure` signature change every user story's bars
depend on. Nothing here adds reference lines or coloring yet.

- [X] T001 [P] Write failing unit tests in `tests/unit/test_risk_chart.py` for a pure
  `bucket_histogram(histogram: list[tuple[int, int]]) -> list[tuple[int, int]]` (bucket center bp,
  summed count) in `src/pages/_risk_chart.py`: `[(-25, 1), (-24, 2), (-3, 4), (0, 12), (7, 9), (65, 1)]`
  groups to `[(-25, 3), (-5, 4), (5, 21), (65, 1)]` (bucket centers -25/-5/5/65 per research.md #2's
  `(bp // 10) * 10 + 5` — verify the exact expected centers by hand before asserting); an empty
  list returns `[]`; a single value returns a single bucket with that value's own count. Run and
  confirm they fail (function doesn't exist yet).
- [X] T002 Create `bucket_histogram` in `src/pages/_risk_chart.py` implementing the `(bp // 10) * 10`
  grouping from research.md #2 (T001 passes). Keep it a standalone, exported pure function (not
  nested inside `build_figure`) so it stays independently unit-testable.
- [X] T003 [P] Write a failing unit test in `tests/unit/test_risk_chart.py` —
  `test_build_figure_signature_accepts_statistics` — asserting `build_figure` now requires a
  second positional/keyword `statistics: HistogramStatistics` argument (construct a minimal
  `HistogramStatistics` with `std_dev_bands=[]`) and still returns a `go.Figure`. Run and confirm
  it fails (`TypeError`: old signature only takes one argument).
- [X] T004 Update `build_figure`'s signature in `src/pages/_risk_chart.py` to
  `build_figure(histogram, statistics: HistogramStatistics) -> go.Figure`, importing
  `HistogramStatistics` from `src.models.portfolio_analysis`. Route the bars through
  `bucket_histogram(histogram)` first (bars now use bucket centers/summed counts, not raw pairs —
  this alone satisfies FR-001; percent-axis/coloring/reference lines are added by the user-story
  tasks below). Confirm T001, T003 pass.
- [X] T005 Update the one call site in `src/pages/risk.py::_render_chart_and_table`:
  `build_figure(response.histogram)` → `build_figure(response.histogram, response.statistics)`.
- [X] T006 Run `python -m pytest tests/unit/test_risk_chart.py -q`; confirm
  `test_build_figure_maps_pairs_to_bar_x_and_y` and `test_build_figure_empty_histogram_produces_empty_trace`
  (feature 024's original tests, which don't pass `statistics` and assert raw un-bucketed x-values)
  now fail as expected — **rewrite them** in place to call `build_figure(histogram, statistics)`
  with a minimal statistics fixture and assert bucketed x-values, rather than leaving them broken;
  this is expected churn to an existing test file, not new coverage, so it is folded into this
  foundational phase rather than a separate story.

**Checkpoint**: `build_figure` groups into 10bp buckets and accepts `statistics`; no percent axis,
reference lines, or coloring yet. The chart still renders (bars just have fewer, wider positions
than before, still labeled in bp) — no user-visible regression beyond a smaller bar count.

---

## Phase 3: User Story 1 — Read the Distribution Shape at a Glance (Priority: P1) 🎯 MVP

**Goal**: The chart shows visibly fewer, wider bars (10bp/0.1% grouping) and its X-axis is
labeled/scaled in percent instead of basis points.

**Independent Test**: Open the Risk page for an account with return history; verify the histogram
shows noticeably fewer bars than one-per-basis-point and the X-axis reads in percent.

### Tests for User Story 1 (write first; must fail)

- [X] T007 [P] [US1] Write failing unit tests in `tests/unit/test_risk_chart.py`:
  `test_build_figure_bars_use_percent_centers` — for histogram `[(-25, 1), (-24, 2), (7, 9)]` and
  a minimal statistics fixture, the resulting `figure.data[0].x` equals `[-0.25, 0.05]`, i.e. each
  bucket's center bp (-25, 5) divided by 100 (research.md #1's `(bp // 10) * 10 + 5) / 100`) — note
  the bucket for -25/-24 is centered at -25 (since `(-25 // 10) * 10 + 5 == -25`) while 7 buckets to
  center 5 (`(7 // 10) * 10 + 5 == 5`); double-check both centers arithmetically before asserting.
  Also assert `figure.data[0].width == 0.1` and `figure.layout.xaxis.ticksuffix == "%"`.
- [X] T008 [US1] Update `tests/bdd/steps/test_risk_steps.py::bar_chart_displayed` (per
  contracts/ui-contract.md's "BDD step impact" note): replace the raw-bp x-value assertion with one
  computed from `stub_client._histogram` via the same bucketing/percent-conversion the production
  code uses (import `bucket_histogram` from `src.pages._risk_chart` in the step rather than
  re-deriving the math independently, so the test can't silently drift from the implementation).
  Run `pytest tests/bdd -k risk --collect-only` to confirm the step still resolves (execution stays
  skipped without Chrome, per the existing environment limitation — record this, don't claim a
  pass you didn't observe). **NOT VERIFIED: no Chrome/chromedriver on this machine, so all 15 Risk
  BDD scenarios collect cleanly (confirmed) but remain SKIPPED at execution; red/green was not
  observed. Run on a machine with Chrome.**

### Implementation for User Story 1

- [X] T009 [US1] In `src/pages/_risk_chart.py`, convert each bucketed `(center_bp, count)` pair to
  `(center_bp / 100, count)` for the `go.Bar`'s `x`, add `width=0.1` to the `go.Bar` call, and
  change the X-axis config from `{"title": "Return (bps)", ...}` to
  `{"title": "Return (%)", "ticksuffix": "%", "showgrid": True, "gridcolor": "#e6e6e6"}` (T007
  passes). Update the `hovertemplate` to show the percent value (e.g. `"%{x:.2f}%: %{y} day(s)<extra></extra>"`).
- [X] T010 [US1] Run `python -m pytest tests/unit/test_risk_chart.py -q`; confirm every test in
  the file passes, including the T006-rewritten feature-024 tests and T001/T003/T007's new ones.

**Checkpoint**: US1 is a shippable MVP — the chart is materially more readable (fewer, wider bars,
percent axis) with no reference lines or coloring yet.

---

## Phase 4: User Story 2 — See Mean and Median at a Glance (Priority: P2)

**Goal**: Two distinguishable vertical reference lines mark the mean and median return.

**Independent Test**: Open the Risk page for an account with a mean distinct from its median;
verify two vertical lines appear, one at each value, visually distinguishable from each other.

### Tests for User Story 2 (write first; must fail)

- [X] T011 [US2] Write failing unit tests in `tests/unit/test_risk_chart.py`:
  `test_build_figure_adds_mean_and_median_vlines` — construct a statistics fixture with
  `mean=10.0, median=-5.0`, call `build_figure`, and assert `figure.layout.shapes` contains exactly
  two vertical-line shapes (`type == "line"`) whose `x0 == x1` equal `0.10` and `-0.05` respectively
  (mean/100, median/100); assert the two shapes have different `line.dash` or `line.color` from
  each other. A second test, `test_build_figure_draws_both_lines_when_mean_equals_median`, asserts
  two shapes are still present (not deduplicated to one) when `mean == median`.

### Implementation for User Story 2

- [X] T012 [US2] In `src/pages/_risk_chart.py`, add two `fig.add_vline(...)` calls after the bar
  trace is added: one at `x=statistics.mean / 100` with one `line_dash`/color and
  `annotation_text="Mean"`, one at `x=statistics.median / 100` with a different `line_dash`/color
  and `annotation_text="Median"` (research.md #4). Confirm T011 passes.
- [X] T013 [US2] Run `python -m pytest tests/unit/test_risk_chart.py -q`; confirm all tests pass,
  including US1's.

**Checkpoint**: US1 and US2 both independently verified — chart is bucketed, percent-scaled, and
now shows mean/median reference lines.

---

## Phase 5: User Story 3 — Assess How Typical or Extreme Returns Are (Priority: P3)

**Goal**: Bars are colored by which standard-deviation band their center falls in (mid-green /
mid-yellow / mid-orange / red), with a single neutral fallback when std dev is undefined.

**Independent Test**: Open the Risk page for an account with a computed standard deviation; verify
bars within 1 sigma are mid-green, progressively further-out bars are mid-yellow/mid-orange/red,
and the boundaries line up with the statistics table's own std-dev figures.

### Tests for User Story 3 (write first; must fail)

- [X] T014 [P] [US3] Write failing unit tests in `tests/unit/test_risk_chart.py` for a pure
  `_color_for_bucket(center_bp: int, std_dev_bands: list[StdDevBand]) -> str` in
  `src/pages/_risk_chart.py`: with bands `sigma=1 (lower=-10, upper=18)`, `sigma=2 (lower=-24,
  upper=32)`, `sigma=3 (lower=-38, upper=46)` (the OpenAPI example from feature 024's contract),
  assert a center of `0` (within sigma=1) returns the mid-green constant; a center of `25`
  (outside sigma=1, within sigma=2) returns mid-yellow; a center of `40` (outside sigma=2, within
  sigma=3) returns mid-orange; a center of `50` (outside sigma=3) returns red; an empty
  `std_dev_bands` list returns the neutral gray constant regardless of `center_bp`.
- [X] T015 [P] [US3] Write a failing unit test in `tests/unit/test_risk_chart.py` —
  `test_build_figure_colors_bars_per_band` — a statistics fixture with the same three bands as
  T014 and a histogram spanning all four color zones; assert `figure.data[0].marker.color` is a
  list (not a single string) whose values match `_color_for_bucket` applied to each bucket's own
  center, in bucket order.
- [X] T016 [US3] Write a failing unit test in `tests/unit/test_risk_chart.py` —
  `test_build_figure_uses_neutral_color_when_std_dev_undefined` — a statistics fixture with
  `std_dev_bands=[]`; assert every entry in `figure.data[0].marker.color` equals the single neutral
  gray constant (FR-006).

### Implementation for User Story 3

- [X] T017 [US3] In `src/pages/_risk_chart.py`, add named color constants
  (`_BAND_1_COLOR`/`_BAND_2_COLOR`/`_BAND_3_COLOR`/`_OUTSIDE_BANDS_COLOR`/`_NO_STD_DEV_COLOR`) per
  data-model.md's Band Color Mapping table, and implement `_color_for_bucket(center_bp,
  std_dev_bands)`: iterate bands in ascending `sigma` order, return the mapped color for the first
  band whose `lower <= center_bp <= upper`; if no band matches (bands non-empty but center outside
  every one), return `_OUTSIDE_BANDS_COLOR`; if `std_dev_bands` is empty, callers use
  `_NO_STD_DEV_COLOR` for every bar instead of calling this function per-bucket (T014 passes).
- [X] T018 [US3] In `build_figure`, replace the single `marker={"color": "#1f77b4"}` with a
  per-bucket color list: `_NO_STD_DEV_COLOR` repeated for every bucket when
  `statistics.std_dev_bands` is empty, otherwise `[_color_for_bucket(center, statistics.std_dev_bands)
  for center in bucket_centers_bp]` (T015, T016 pass). Keep the color list computed from bucket
  **center bp** values (pre-percent-conversion), per research.md #3 and FR-007.
- [X] T019 [US3] Run `python -m pytest tests/unit/test_risk_chart.py -q`; confirm every test in the
  file passes (US1, US2, US3 combined).

**Checkpoint**: All three user stories independently verified — bucketed percent axis, mean/median
lines, and std-dev band coloring all present together with no regressions to earlier stories.

---

## Phase 6: Polish & Cross-Cutting

- [X] T020 [P] Run `ruff check .` and `mypy .` from `portfolio-browser/`; fix any findings in
  files touched by this feature.
- [ ] T021 Follow `specs/025-risk-histogram-rendering/quickstart.md` manually against a running
  `portfolio-analysis-service`; confirm every step and record the result in the PR description. If
  the endpoint is unavailable, say so explicitly rather than reporting this as done. **NOT
  VERIFIED: no running portfolio-analysis-service instance in this environment. Run manually
  before merging.**
- [X] T022 Run the full existing test suite (`python -m pytest tests/unit tests/bdd -q`) to confirm
  no regression outside the Risk page's own tests (e.g. `test_callback_registration.py` still
  passes since `risk.py`'s only change is the one-line `build_figure` call). 243/243 unit tests
  pass; the full BDD suite (155 scenarios) collects cleanly and skips uniformly for lack of Chrome
  — the same pre-existing environment limitation, not a regression from this feature.

---

## Dependencies & execution order

- Phase 1: no tasks.
- Phase 2 (T001–T006) blocks every user story: T001→T002 sequential; T003→T004 sequential (both
  touch `build_figure`, so T002 and T004 together are one coherent edit to the same function,
  done as two focused steps); T005 depends on T004; T006 depends on T004/T005.
- US1 needs Phase 2 complete. T007 parallel with T008 (different files); T009 depends on T007;
  T010 last.
- US2 needs Phase 2 complete (does not depend on US1, but ships after it per priority order). T011
  first; T012 depends on T011; T013 last.
- US3 needs Phase 2 complete (does not depend on US1/US2, but ships after them per priority
  order). T014 and T015/T016 can be written in parallel (different test functions, same file — not
  marked [P] against each other since they share a file, but have no logical dependency); T017
  depends on T014; T018 depends on T015, T016, T017; T019 last.
- Polish after US3.

### Parallel examples

```text
Phase 2: T001 + T003            (different functions/tests, no shared state yet)
US1:     T007 + T008            (test_risk_chart.py vs test_risk_steps.py)
US3:     T014 + T015 + T016     (independent test functions; combine into one PR-sized edit)
Polish:  T020 (only polish task besides sequential T021/T022)
```

## Implementation strategy

1. **MVP = Phase 2 + US1** (T001–T010): the chart is bucketed and percent-scaled — the core
   readability fix. Stop and demo here if needed.
2. **US2** adds mean/median reference lines.
3. **US3** adds std-dev band coloring.
4. **Polish** then manual verification against the real service.

## Task summary

- Total: 22 tasks — Foundational 6, US1 4 (T007–T010), US2 3 (T011–T013), US3 6 (T014–T019), Polish 3.
- Test tasks (written first): T001, T003, T007, T008, T011, T014, T015, T016.
