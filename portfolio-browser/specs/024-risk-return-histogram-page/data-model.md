# Phase 1 Data Model: Risk Page (Return Histogram)

All entities below are read-only view models deserialized from
`GET /v1/accounts/{account_name}/risk/return-histogram` (portfolio-analysis-service, spec 011) —
no calculation happens client-side (Principle I). Field names/types are verified against
`portfolio-analysis-service/app/models/risk.py`, not assumed.

## StdDevBand

One standard-deviation band around the mean, in basis points. **Not rendered by this feature**
(spec explicitly excludes `std_dev_bands` from the table) — modeled here only because it is a
required nested field of `HistogramStatistics` and must validate.

| Field | Type | Notes |
|---|---|---|
| `sigma` | `int` | 1, 2, or 3 |
| `multiple` | `float` | `sigma x std_dev` |
| `lower` | `float` | `mean - multiple` |
| `upper` | `float` | `mean + multiple` |

## HistogramStatistics

Summary statistics over the same rounded basis-point observations as the histogram.

| Field | Type | Notes | Table row order |
|---|---|---|---|
| `count` | `int` | Number of observations (business days) | 1 |
| `mean` | `float \| None` | Basis points; `None` when `count == 0` | 2 |
| `median` | `float \| None` | Basis points; `None` when `count == 0` | 3 |
| `mode` | `int \| None` | Most frequent bucket (smallest on ties); `None` when `count == 0` | 4 |
| `minimum` | `int \| None` | `None` when `count == 0` | 5 |
| `maximum` | `int \| None` | `None` when `count == 0` | 6 |
| `std_dev` | `float \| None` | `None` when `count < 2` | 7 |
| `std_dev_bands` | `list[StdDevBand]` | **Excluded from the table** (FR-010) | — |
| `skewness` | `float \| None` | `None` when `count < 3` or `std_dev == 0` | 8 |
| `kurtosis` | `float \| None` | `None` when `count < 4` or `std_dev == 0` | 9 |

A `None` value in any of rows 1–9 renders as a fixed "N/A" placeholder (FR-012), never as an
omitted row.

## ReturnHistogramResponse

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | Echoed selected account |
| `from_date` | `date` | Resolved start of the observation window |
| `to_date` | `date` | Resolved end of the observation window |
| `histogram` | `list[tuple[int, int]]` | `[basis_point_bucket, day_count]` pairs, ascending by bucket; buckets with 0 observations omitted by the service |
| `statistics` | `HistogramStatistics` | See above |
| `links` | `dict[str, str]` | HATEOAS links (`_links` on the wire); not rendered by this page, mirroring how `TimeSeriesResponse.links` is parsed but unused by chart-only pages |

## Histogram Bucket (chart entity)

Not a separate model class — each `histogram` tuple is consumed directly by the chart builder:
first element → X-axis category (basis points), second element → bar height (day count).

## Reporting Period Shortcut (extended)

Existing entity (`src/components/date_range_controls.py`, spec 017) — this feature adds one new
value to the fixed set:

| Code | Offset | Introduced by |
|---|---|---|
| `SHORTCUT_10Y` (`"10y"`) | 10 years before the end date | This feature |
| `SHORTCUT_1Y`, `SHORTCUT_3Y`, `SHORTCUT_5Y`, `SHORTCUT_ALL` | (unchanged) | Prior features |

`SHORTCUT_YTD` remains defined and used by Overview/Positions; this page never references it — its
first shortcut slot is relabeled "10Y" and mapped to `SHORTCUT_10Y` instead, the same way
Performance's first slot is relabeled "ITD" and mapped to `SHORTCUT_ALL`.

## Navigation Section (extended)

Existing entity (`config/content.yaml` → `NavigationSection`) — this feature adds one new
`nav_sections` entry (`key: risk`, `label: Risk`), no schema change.
