# UI Contract: Risk Histogram Chart (rendering-only update)

No external API contract changes — this feature consumes the same
`GET /v1/accounts/{account_name}/risk/return-histogram` response feature 024 already contracted
against (`portfolio-analysis-service/specs/011-risk-return-histogram/contracts/openapi.yaml`).
This document specifies only the internal function contract that changes.

## `src/pages/_risk_chart.py::build_figure`

**Before** (024): `build_figure(histogram: list[tuple[int, int]]) -> go.Figure`

**After** (this feature):

```python
def build_figure(
    histogram: list[tuple[int, int]],
    statistics: HistogramStatistics,
) -> go.Figure:
    ...
```

- `histogram`: unchanged — the raw `[basis_point_bucket, day_count]` pairs from
  `ReturnHistogramResponse.histogram`.
- `statistics`: new parameter — the same `HistogramStatistics` object already passed to
  `_risk_table.py::build_rows` at the same call site, supplying `mean`, `median`, and
  `std_dev_bands`.

**Behavior**:

1. Groups `histogram`'s raw pairs into contiguous 10bp buckets (research.md #2), summing counts.
2. Plots one `go.Bar` per non-empty bucket, `x` = bucket center in percent, `width=0.1`.
3. Colors each bar per the Band Color Mapping in data-model.md, using `statistics.std_dev_bands`;
   every bar uses the single neutral fallback color when `std_dev_bands` is empty.
4. Adds two `add_vline` reference lines at `statistics.mean / 100` and `statistics.median / 100`,
   each independently styled and labeled.
5. Sets the X-axis title/format to a percent-suffixed numeric axis (research.md #1) in place of
   the previous "Return (bps)" title.

**Unchanged**: the Y-axis ("Days"), the overall `plotly_white` template/font/margins, and every
other Risk-page component (statistics table, account/date controls, callbacks, route).

## Call site: `src/pages/risk.py::_render_chart_and_table`

**Before**:

```python
figure=build_figure(response.histogram)
```

**After**:

```python
figure=build_figure(response.histogram, response.statistics)
```

No other line in `risk.py` changes.

## BDD step impact

`tests/bdd/steps/test_risk_steps.py::bar_chart_displayed` currently asserts the chart's plotted
`x` values equal the fake histogram's raw bp pairs verbatim. This step must be updated to assert
bucketed, percent-scaled `x` values instead (or a new/renamed step added and the old one retired),
since the raw-value assertion no longer holds once bucketing ships.
