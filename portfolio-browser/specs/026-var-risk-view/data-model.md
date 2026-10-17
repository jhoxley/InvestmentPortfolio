# Data Model: Value at Risk View (Risk Page)

No new persisted storage — every entity below is a client-side Pydantic model (mirroring, as a
subset where noted, `portfolio-analysis-service`'s own 012/013 response shapes) plus the
in-browser `dcc.Store` payload shape the two callbacks (research.md #1) exchange. All model
additions live in `src/models/portfolio_analysis.py`.

## ConfidenceLevelEstimate

Mirrors `portfolio-analysis-service`'s model of the same name (013) exactly — one confidence
level's VaR/ES and exception flags for one series entry.

| Field | Type | Notes |
|---|---|---|
| `confidence_bp` | `int` | e.g. `9500` |
| `var_gbp` | `float \| None` | `None` if quality `insufficient` |
| `var_pct` | `float \| None` | |
| `es_gbp` | `float \| None` | |
| `es_pct` | `float \| None` | |
| `hypothetical_exception` | `bool \| None` | |
| `ladder_exception` | `bool \| None` | |

## VarSeriesEntry

Mirrors 013's model of the same name. One business date's estimate joined with its outcome.

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | As-of date |
| `outcome_date` | `date` | The date the PnL bar is plotted at (FR-004) |
| `total_value_gbp` | `float` | Feeds the linked market-value chart (FR-008) |
| `scenario_count` | `int` | Not displayed; carried for completeness |
| `actual_mv_pct` | `float` | |
| `proxied_mv_pct` | `float` | Feeds the linked chart's proxied/rescaled share (FR-008) |
| `rescaled_mv_pct` | `float` | |
| `quality` | `Literal["ok","degraded","insufficient"]` | Drives the hide-degraded toggle (US6) |
| `quality_reason` | `str \| None` | Not displayed |
| `hypothetical_pnl_gbp` | `float \| None` | `None` if outcome pending |
| `ladder_pnl_gbp` | `float \| None` | |
| `levels` | `list[ConfidenceLevelEstimate]` | |

## VarSeriesResponse

Mirrors 013's model of the same name.

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | |
| `lookback_code` | `str` | |
| `lookback_days` | `int` | Not displayed |
| `from_date` | `date` | |
| `to_date` | `date` | |
| `series` | `list[VarSeriesEntry]` | |
| `links` | `dict[str, str]` | alias `_links`; `status`/`runs` used by FR-013/FR-014's guidance text |

## RollingExceptionPoint / BacktestConfidenceResult / VarBacktestResponse

Mirror 013's models of the same names exactly (`rolling_exceptions` is always `None` here, since
this view never requests the rolling option — Assumptions). `BacktestConfidenceResult` supplies
every field FR-009 needs: `observation_count`, `exception_count`, `expected_exceptions`,
`exception_rate`, `kupiec_lr`/`kupiec_p_value`, `christoffersen_independence_lr`/`_p_value`,
`conditional_coverage_lr`/`_p_value`, `zone`, `exception_dates`, `mean_var_gbp`, `var_stability`.

## MethodLookback / VarMethodsResponse

Mirror 013's models of the same names. `VarMethodsResponse.lookbacks` (with `is_headline`) and
`.confidence_levels_bp` populate the VaR tab's own controls (FR-002/FR-003); `.measures` is not
displayed by this view.

## VarStatusSummary (new — a deliberate subset of 012's `VarStatus`)

| Field | Type | Notes |
|---|---|---|
| `account_name` | `str` | |
| `computed_range` | `DateRange \| None` | `None` → "never computed" (FR-013's empty state) |
| `missing_dates` | `int` | The banner's count (FR-014) |
| `links` | `dict[str, str]` | alias `_links`; `runs` link referenced by the empty state's guidance text |

`DateRange` (`from_date: date`, `to_date: date`) is a small nested model, also new.

Only these fields are modeled, not every field 012's `VarStatus` exposes (`stale_dates_last_run`,
`pending_outcomes`, `last_run`, `instruments`, `warnings`) — this view has no use for them, and
Pydantic's default `extra="ignore"` lets the client validate the fuller real response against this
narrower model without error, the same partial-modeling precedent `StdDevBand`/`HistogramStatistics`
already set for the histogram response.

## `dcc.Store(id="risk-var-store")` payload shape

The fetch callback's single combined write, read only by the render callback:

```text
{
  "account_name": str,
  "lookback_code": str,
  "series": VarSeriesResponse (as dict, via model_dump(mode="json")),
  "backtest": {
    "hypothetical": { "ok": VarBacktestResponse, "degraded": VarBacktestResponse },
    "ladder":       { "ok": VarBacktestResponse, "degraded": VarBacktestResponse }
  },
  "status": VarStatusSummary (as dict),
  "fetch_error": str | None   # set instead of the above four keys on any fetch failure
}
```

## `dcc.Store(id="risk-var-methods-store")` payload shape

```text
VarMethodsResponse (as dict), or {"fetch_error": str} on failure
```

## Relationships

```text
GET /v1/risk/var/methods ──────────────────────► risk-var-methods-store ──► _var_controls.py
                                                                                   │
GET .../risk/var (series, once) ───────────┐                                      │ (selected
GET .../risk/var/backtest (×4) ────────────┼──► risk-var-store ──► render callback │  confidence/
GET .../risk/var/status (once) ────────────┘         ▲                 │           │  units/basis/
                                                       │                 ▼           │  degraded/ES)
                                      fetch callback (account/date/look-back)   _var_chart.py
                                                                                 _var_backtest_panel.py
```

No state transitions — every entity is derived fresh on each fetch from the already-immutable
(per computed run) upstream store `portfolio-analysis-service` maintains.
