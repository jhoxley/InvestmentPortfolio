# Implementation Plan: Readable Return Histogram Rendering

**Branch**: `025-risk-histogram-rendering` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/025-risk-histogram-rendering/spec.md`

## Summary

Rework `src/pages/_risk_chart.py::build_figure` (introduced by feature 024, currently one bar per
raw basis-point value) into a four-part pure transform: (1) group the raw `[bp, count]` pairs into
contiguous 10bp buckets, summing counts; (2) render bucket centers on a percent-scaled X-axis
instead of raw basis points; (3) add two `go.Figure.add_vline` reference lines at the response's
mean and median return; (4) color each bar by which `std_dev_bands` entry (if any) contains its
bucket center, falling back to one neutral color when `std_dev_bands` is empty (std dev
undefined). `build_figure`'s signature grows from `(histogram)` to `(histogram, statistics)`; its
one call site in `risk.py::_render_chart_and_table` passes `response.statistics` in addition to
`response.histogram`. No API, model, or other Risk-page UI change.

## Technical Context

**Language/Version**: Python 3.11+ (existing project)
**Primary Dependencies**: Plotly (existing; no new dependency) — `go.Figure.add_vline` is a
standard Plotly Graph Objects method already available in the pinned `plotly>=5` requirement
**Storage**: N/A
**Testing**: pytest (existing `tests/unit/test_risk_chart.py`, extended)
**Target Platform**: Desktop/tablet browsers via the existing Dash app
**Project Type**: Web application (Dash UI over `portfolio-analysis-service`)
**Performance Goals**: Purely client-rendering-side; no new network calls or added latency
**Constraints**: Must pass `ruff` and `mypy`; must not change `ReturnHistogramResponse`'s wire
shape, the statistics table, or any callback signature in `risk.py` beyond the one call site
**Scale/Scope**: 1 file rewritten (`_risk_chart.py`), 1 one-line call-site update (`risk.py`), unit
tests extended

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1 — still passing.*

| Principle | Assessment |
|-----------|------------|
| I. API-sourced data, no local business logic | PASS. Bucketing, band-membership lookup, and reference-line positioning are pure *presentational* transforms of already-fetched values (grouping/re-labeling for display) — no new financial calculation. The `std_dev_bands`, `mean`, and `median` values themselves still come entirely from the API, unchanged. |
| II. Layered API architecture | N/A. No service-layer or API change. |
| III. Test-first BDD | PASS. `tests/unit/test_risk_chart.py` gets new failing tests for bucketing, axis scaling, reference lines, and band coloring before the rewrite; the existing `risk_view_histogram.feature` BDD scenario asserting bar x-values is updated to match the new bucketed/percent-scaled output. |
| IV. Configuration over hard-coding | PASS. The four band colors + neutral fallback are named constants in `_risk_chart.py` (this page's only consumer), not user-configurable/environment-specific values — consistent with `PERFORMANCE_ATTRIBUTE_COLORS`'s own precedent of a fixed in-code color mapping rather than a config-file entry. |
| V. Standard libraries / SOLID / static analysis | PASS. Uses Plotly's own `add_vline` rather than hand-drawn shapes; bucketing is a small pure function, not a new dependency. `ruff` + `mypy` must stay clean. |
| UX standards | PASS. Purely improves chart readability; no new interaction, no new loading state. |

No violations, so the Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/025-risk-histogram-rendering/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── ui-contract.md   # Phase 1 output (chart-only; no API contract change)
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks (not this command)
```

### Source Code (repository root: `portfolio-browser/`)

```text
src/
└── pages/
    ├── _risk_chart.py   # rewritten: bucketing, percent axis, vlines, band coloring
    └── risk.py           # one-line call-site update: build_figure(histogram, statistics)

tests/
├── unit/
│   └── test_risk_chart.py   # extended: bucketing, axis, vlines, coloring, no-std-dev fallback
└── bdd/
    └── steps/test_risk_steps.py   # `bar_chart_displayed` step updated for bucketed x-values
```

**Structure Decision**: No new files. This is a rewrite of a single existing pure-function module
plus its one call site, following the same file-per-concern boundary feature 024 already
established (`_risk_chart.py` stays a plain, Dash-free, unit-testable module).

## Design Notes

- **Bucketing**: `bucket_key(bp) = (bp // 10) * 10` (Python's `//` floors toward negative
  infinity, giving contiguous, non-overlapping 10-wide bins across positive and negative values
  alike, e.g. bp=-25 → bucket -30..-21, bp=7 → bucket 0..9). Bucket center = `bucket_key + 5`.
  Counts for every raw pair whose bp falls in the same bucket are summed (FR-001).
- **Percent axis**: 1 basis point = 0.01%, so a bucket center in bp is displayed as
  `center_bp / 100` (e.g. center -25.5bp → -0.255, meaning "-0.255%"). Rather than Plotly's
  fraction-based `tickformat=".1%"` (which would require passing 0.00255-style fractions and
  double-multiply), the X-axis renders the already-percent numeric value directly with
  `ticksuffix="%"` and title "Return (%)" — avoiding a second, easy-to-get-wrong scale conversion
  (research.md #1).
- **Bar width**: `go.Bar(x=centers_percent, ..., width=0.1)` (0.1 percentage points, matching the
  10bp bucket width in the same percent units as `x`) so adjacent bars visually touch with no gap
  suggesting missing data.
- **Reference lines**: `fig.add_vline(x=statistics.mean/100, ...)` and
  `fig.add_vline(x=statistics.median/100, ...)`, each with its own `line_dash`/color and an
  `annotation_text` ("Mean"/"Median") so they remain distinguishable even when equal/overlapping
  (FR-003, FR-004) — Plotly draws both regardless of overlap since they are independent shapes.
- **Band coloring**: for each bucket, find the smallest-sigma `StdDevBand` whose
  `lower <= bucket_center_bp <= upper`; map sigma 1→mid-green, 2→mid-yellow, 3→mid-orange, no
  match (outside every band, sigma 3's own upper/lower)→red. When `statistics.std_dev_bands` is
  empty (std dev undefined per the API contract), every bar uses one neutral gray instead
  (FR-006). This is per-bucket, not per-raw-observation, so FR-007's "exactly one color per bar"
  holds by construction — the coloring function only ever sees the bucket's single center value.
- **`build_figure` signature change**: `build_figure(histogram, statistics)`. The one call site
  (`risk.py::_render_chart_and_table`) already has `response.statistics` in scope (it already
  passes `response.statistics` to `_risk_table.build_rows` on the very next line), so this is a
  same-function, no-new-plumbing change.

## Risks

- Changing `build_figure`'s signature is a breaking change to any other caller — grep confirms
  `risk.py` is the only caller, so this is safe within this codebase.
- The existing BDD step `bar_chart_displayed` (`tests/bdd/steps/test_risk_steps.py`) asserts raw
  `x` values equal the fake histogram's raw bp pairs; it must be updated to assert bucketed,
  percent-scaled values against the fake data used in that scenario, or it will fail once this
  ships (task list must include this).
- Floating-point bucket-center/percent conversions (`bp / 100`, `(bp // 10) * 10 + 5`) need exact
  test assertions using values that divide cleanly, to avoid flaky float-equality assertions in
  unit tests.
