# Data Model: VaR Series, Backtest and Methods Endpoints

No new persisted storage. Every entity below is a **response-shaping Pydantic model**
built by reading feature 012's existing `estimates.csv` / `outcomes.csv` (via the
existing `VarRepository`) and `VarSettings`. All live in the new
`app/models/var_series.py`.

## VarSeriesEntry

One business date's stored estimate (at the requested look-back) joined with its
realised outcome.

| Field | Type | Source | Notes |
|---|---|---|---|
| `date` | `date` | `estimates.date` | As-of date |
| `outcome_date` | `date` | `outcomes.outcome_date` | Next business day the PnL realised on |
| `total_value_gbp` | `float` | `outcomes.total_value_gbp` | |
| `scenario_count` | `int` | `estimates.scenario_count` | |
| `actual_mv_pct` | `float` | `estimates.actual_mv_pct` | |
| `proxied_mv_pct` | `float` | `estimates.proxied_mv_pct` | |
| `rescaled_mv_pct` | `float` | `estimates.rescaled_mv_pct` | |
| `quality` | `Literal["ok","degraded","insufficient"]` | `estimates.quality` | |
| `quality_reason` | `str \| None` | `estimates.quality_reason` | |
| `hypothetical_pnl_gbp` | `float \| None` | `outcomes.hypothetical_pnl_gbp` | `None` if outcome pending |
| `ladder_pnl_gbp` | `float \| None` | `outcomes.ladder_pnl_gbp` | `None` if outcome pending |
| `levels` | `list[ConfidenceLevelEstimate]` | derived | One per requested confidence level |

**Validation**: None beyond type coercion — this is a read-through of already-validated
stored data (feature 012 validated it at write time).

## ConfidenceLevelEstimate

Nested in `VarSeriesEntry.levels`, one per requested confidence level.

| Field | Type | Source | Notes |
|---|---|---|---|
| `confidence_bp` | `int` | requested level | e.g. `9500` |
| `var_gbp` | `float \| None` | `estimates.var_<bp>_gbp` | `None` if quality `insufficient` |
| `var_pct` | `float \| None` | derived: `var_gbp / total_value_gbp * 100` | `None` under the same condition |
| `es_gbp` | `float \| None` | `estimates.es_<bp>_gbp` | `None` if quality `insufficient` |
| `es_pct` | `float \| None` | derived | `None` under the same condition |
| `hypothetical_exception` | `bool \| None` | derived: `hypothetical_pnl_gbp < -var_gbp` | `None` if either side is `None` |
| `ladder_exception` | `bool \| None` | derived: `ladder_pnl_gbp < -var_gbp` | `None` if either side is `None` |

## VarSeriesResponse

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | |
| `lookback_code` | `str` | The resolved look-back actually used (e.g. `"2y"`) |
| `lookback_days` | `int` | Its configured business-day length |
| `from_date` | `date` | Resolved window start |
| `to_date` | `date` | Resolved window end |
| `series` | `list[VarSeriesEntry]` | Empty if nothing computed (FR-008) — never an error |
| `_links` | `dict[str, str]` | `self`; always `status`, `runs` (FR-008, FR-025) |

## BacktestConfidenceResult

One per requested confidence level.

| Field | Type | Notes |
|---|---|---|
| `confidence_bp` | `int` | |
| `observation_count` | `int` | `N`; always numeric, `0` if none |
| `exception_count` | `int` | `x`; always numeric, `0` if none |
| `expected_exceptions` | `float \| None` | `N * (1 - confidence)`; `None` only if `N == 0` |
| `exception_rate` | `float \| None` | `x / N`; `None` if `N == 0` |
| `kupiec_lr` | `float \| None` | research.md §8 |
| `kupiec_p_value` | `float \| None` | |
| `christoffersen_independence_lr` | `float \| None` | |
| `christoffersen_independence_p_value` | `float \| None` | |
| `conditional_coverage_lr` | `float \| None` | |
| `conditional_coverage_p_value` | `float \| None` | |
| `zone` | `Literal["green","yellow","red"] \| None` | `None` only if `N == 0` |
| `exception_dates` | `list[date]` | May be empty |
| `mean_var_gbp` | `float \| None` | Mean of `var_gbp` over the observation set; `None` if `N == 0` |
| `var_stability` | `float \| None` | research.md §8; `None` if fewer than 2 qualifying log-changes |
| `rolling_exceptions` | `list[RollingExceptionPoint] \| None` | Only present (non-`None`) when the rolling option was requested |

## RollingExceptionPoint

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | The window's last included date |
| `exception_count` | `int` | Exceptions in the trailing 250 included observations ending at `date` |

## VarBacktestResponse

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | |
| `lookback_code` | `str` | |
| `lookback_days` | `int` | |
| `from_date` | `date` | |
| `to_date` | `date` | |
| `pnl_basis` | `Literal["hypothetical","ladder"]` | Echoes the resolved parameter |
| `min_quality` | `Literal["ok","degraded"]` | Echoes the resolved parameter |
| `levels` | `list[BacktestConfidenceResult]` | |
| `_links` | `dict[str, str]` | `self`; always `status`, `runs` |

## MethodLookback

| Field | Type | Notes |
|---|---|---|
| `code` | `str` | e.g. `"1y"` |
| `business_days` | `int` | e.g. `260` |
| `is_headline` | `bool` | `True` for `settings.headline_lookback` |

## VarMethodsResponse

| Field | Type | Notes |
|---|---|---|
| `method` | `str` | Fixed: `"historical-simulation"` |
| `methodology_version` | `str` | `settings.methodology_version` |
| `lookbacks` | `list[MethodLookback]` | One per `settings.lookbacks` entry |
| `confidence_levels_bp` | `list[int]` | `settings.confidence_levels_bp` |
| `measures` | `list[str]` | Static list (research.md §9) |
| `_links` | `dict[str, str]` | `self` only — no account scope |

## Relationships

```text
VarSettings (config, in-memory)
   └── VarMethodsResponse (pure function)

VarRepository.read_estimates(account) ──┐
VarRepository.read_outcomes(account)  ──┼──► join on `date` ──► VarSeriesEntry[]
                                         │                         │
                                         └─────────────────────────┴──► observation set
                                                                         (quality/pending
                                                                          filtered, §6)
                                                                              │
                                                                              ▼
                                                              BacktestConfidenceResult[]
                                                              (via app/services/var/backtest.py,
                                                               pure functions over the
                                                               observation set)
```

No state transitions — every entity here is derived fresh on each request from
already-persisted, immutable (per run) store rows.
