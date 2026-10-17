# Phase 1 Data Model: Readable Return Histogram Rendering

No new wire-level entities — this feature derives new *presentation-only* structures from the
existing `ReturnHistogramResponse`/`HistogramStatistics`/`StdDevBand` models (feature 024,
`src/models/portfolio_analysis.py`), unchanged here.

## Grouped Histogram Bucket (new, presentation-only)

Computed inside `_risk_chart.py`; never serialized, never sent back to any API.

| Field | Type | Derivation |
|---|---|---|
| `bucket_key` | `int` (bp) | `(bp // 10) * 10` for each raw `[bp, count]` pair |
| `center_bp` | `int` | `bucket_key + 5` |
| `center_percent` | `float` | `center_bp / 100` — the value actually plotted on the X-axis |
| `count` | `int` | Sum of every raw pair's count whose `bucket_key` matches |
| `color` | `str` (hex) | See Band Color Mapping below |

Buckets are produced in ascending `bucket_key` order, one bar per non-empty bucket (a bucket with
zero total count is omitted, mirroring the raw API's own "buckets with no observations are
omitted" convention).

## Band Color Mapping (new, presentation-only, fixed constants in `_risk_chart.py`)

| Condition (on a bucket's `center_bp`) | Color role | Example hex (planning default) |
|---|---|---|
| Within the sigma=1 band's `lower..upper` | Typical | mid-green, e.g. `#2ca02c` |
| Outside sigma=1 but within sigma=2 | Somewhat unusual | mid-yellow, e.g. `#d4c93b` |
| Outside sigma=2 but within sigma=3 | Unusual | mid-orange, e.g. `#ff7f0e` |
| Outside sigma=3, or `std_dev_bands` non-empty but center matches none | Extreme | red, e.g. `#d62728` |
| `std_dev_bands` is empty (std dev undefined) | Unknown/insufficient data | neutral gray, e.g. `#7f7f7f`, applied to **every** bar |

Exact hex values are an implementation choice (spec Assumptions); the table above records
planning-time defaults, finalized during implementation.

## Reference Line (new, presentation-only)

| Field | Value |
|---|---|
| Mean line `x` | `statistics.mean / 100` (percent) |
| Median line `x` | `statistics.median / 100` (percent) |
| Distinguishing style | Distinct `line_dash` and/or color per line, each carrying its own
  `annotation_text` ("Mean" / "Median") |

Both lines are always drawn together whenever a chart is rendered (the page's existing "no data"
empty-state already short-circuits before `build_figure` is ever called when `count == 0`, so
`mean`/`median` are never `None` at this point per `HistogramStatistics`'s own contract).

## Updated function signature

`src/pages/_risk_chart.py::build_figure`:

- **Before** (feature 024): `build_figure(histogram: list[tuple[int, int]]) -> go.Figure`
- **After** (this feature): `build_figure(histogram: list[tuple[int, int]], statistics: HistogramStatistics) -> go.Figure`

No other function in the Risk page's callback graph changes signature.
