# Implementation Plan: VaR Series, Backtest and Methods Endpoints

**Branch**: `013-var-series-backtest-api` | **Date**: 2026-10-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-var-series-backtest-api/spec.md`
**Methodology**: [`docs/proposals/value-at-risk.md`](../../docs/proposals/value-at-risk.md) §4

## Summary

Add three strictly read-only endpoints over feature 012's existing per-account VaR store
(`estimates.csv`, `outcomes.csv`); none trigger a calculation:

- `GET /v1/accounts/{account_name}/risk/var` — the time series of previously computed
  VaR/ES estimates joined with their realised outcomes, for a resolved date range, one
  look-back (default the new configured headline) and one or more confidence levels
  (default all).
- `GET /v1/accounts/{account_name}/risk/var/backtest` — Kupiec, Christoffersen
  (independence + conditional coverage) and a Basel-style traffic-light zone per
  confidence level, plus exception dates, mean VaR and VaR stability, filterable by
  `pnl_basis` and `min_quality`, with an optional rolling-250-day exception series.
- `GET /v1/risk/var/methods` — the configured method, look-backs, confidence levels and
  measures, for building UI controls; needs no account.

All statistics use only `math.erfc`, `math.exp` and `math.lgamma` (no new dependency).
Date resolution reuses the same account/ladder validation and defaulting as the
performance endpoints, but — unlike those endpoints — never reads the full ladder file,
since only its date range (already in account metadata) is needed; the two new services
read the lightweight VaR CSVs through the existing `VarRepository`.

## Technical Context

**Language/Version**: Python 3.11+ (mypy checked at `python_version = "3.12"`, per feature 012)
**Primary Dependencies**: FastAPI 0.139, pandas 3.0, numpy 2.5, Pydantic 2.13, structlog
26.1 — all already pinned, no additions. Stdlib: `math.erfc`, `math.exp`, `math.lgamma`.
**Storage**: Filesystem, read-only. Existing `data/{account}/var/estimates.csv` and
`outcomes.csv` via the existing `VarRepository` (feature 012). No schema change, no new
files, no writes from this feature.
**Testing**: pytest unit tests (`tests/unit/`) for the pure statistics module and both
services; pytest-bdd Gherkin (`tests/features/`, `tests/steps/`) for the four user
stories, reusing `var_calculation_runs_steps.py`'s fixtures to seed a store.
**Target Platform**: Locally hosted uvicorn service on Windows (also runs on Linux)
**Project Type**: Single web-service project (existing `app/` layout)
**Performance Goals**: Series or backtest over up to ~10 years of daily data (≤ 2,700
rows) returns in < 2 s (SC-004) — achievable because both endpoints read only the small
per-account CSVs (never the ladder), matching the existing status endpoint's budget.
**Constraints**: Strictly read-only (FR-023) — no calculation run is triggered, no store
write occurs. `insufficient`-quality and pending-outcome dates are never backtest
observations, regardless of `min_quality` (FR-011). Excluded dates break Christoffersen's
transition chain rather than being skipped over (FR-014). Existing endpoints and their
error formats are unchanged.
**Scale/Scope**: 2 real accounts; ≤ 2,700 dates × 3 look-backs × 3 confidence levels per
account; 3 new endpoints, 1 extended router, 2 new service modules, 1 new pure-statistics
module, 1 new models module. No new repository or client.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: The spec has Gherkin scenarios for User Stories 1–4. Tasks will
  place the statistics-module unit tests (Kupiec/Christoffersen/CC/zone against the
  proposal's and spec's hand-worked values — SC-002, SC-003), the series/backtest service
  unit tests, and the BDD steps before their implementation tasks.
- [x] **II. SOLID**:
  - Single-responsibility modules: a pure `backtest.py` (statistics only, no I/O, mirrors
    `engine.py`'s existing pattern), `var_series_service.py` and `var_backtest_service.py`
    (orchestration), a small shared date-window helper, and a trivial `var_methods_service.py`.
  - No existing module is modified for its existing behaviour: `VarRepository`,
    `engine.py`, `var_run_service.py` and `var_status_service.py` are read-only
    dependencies of the new services, untouched.
  - The date-window helper depends on the same `AccountsService` and
    `TimeseriesDateResolver` abstractions the performance/risk endpoints already use
    (no new protocol needed).
- [x] **III. Type Safety**: Full annotations and docstrings; `mypy --strict`; `ruff check`
  and `ruff format`. Pydantic models for every new response body
  (`VarSeriesResponse`, `VarBacktestResponse`, `VarMethodsResponse`) and for the new
  `InvalidVarQueryError`'s structured fields.
- [x] **IV. Observability**: Structured `structlog` events for each request (account,
  look-back, confidence levels requested, observation/exception counts for the backtest),
  mirroring `risk_service.py`'s existing `return_histogram_request` event. Errors use the
  existing `_var_problem()` helper, so the new `InvalidVarQueryError` carries a
  correlation ID (FR-025) exactly as feature 012's new error types do.
- [x] **V. RESTful/OpenAPI**: Resources are read-only nouns (`risk/var`,
  `risk/var/backtest`, `risk/var/methods`); `contracts/openapi.yaml` is updated; every
  response carries `_links` (self, plus status/runs for the account-scoped ones per
  FR-025); the one new error type (`invalid-var-query`, 422) follows RFC 7807; every
  other rejected case (FR-024) reuses feature 012's and the performance endpoints'
  existing error types unchanged.
- [x] **No unjustified violations**: None. No Complexity Tracking entries required.

**Post-design re-check (after Phase 1)**: data-model, contracts and quickstart introduce
no further deviations. All gates still pass.

## Project Structure

### Documentation (this feature)

```text
specs/013-var-series-backtest-api/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml                      # series + backtest + methods endpoints
├── checklists/
│   └── requirements.md
└── tasks.md                              # /speckit-tasks (not created here)
```

### Source Code

```text
app/
├── api/
│   └── risk_var.py                       # MODIFIED — GET series, GET backtest, GET methods
├── models/
│   └── var_series.py                     # NEW — VarSeriesResponse, VarSeriesEntry,
│                                         #   ConfidenceLevelEstimate, VarBacktestResponse,
│                                         #   BacktestConfidenceResult, RollingExceptionPoint,
│                                         #   VarMethodsResponse, MethodLookback
├── services/
│   └── var/
│       ├── backtest.py                   # NEW — pure: kupiec_pof, christoffersen_independence,
│       │                                 #   conditional_coverage, traffic_light_zone,
│       │                                 #   var_stability, rolling_exception_counts
│       ├── var_window.py                 # NEW — resolve_window(): account/ladder validation
│       │                                 #   + date resolution without reading the full ladder
│       ├── var_series_service.py         # NEW — VarSeriesService.get_series()
│       ├── var_backtest_service.py       # NEW — VarBacktestService.get_backtest()
│       └── var_methods_service.py        # NEW — build_methods_response(settings)
├── config.py                             # MODIFIED — VarSettings.headline_lookback
└── exceptions.py                         # MODIFIED — InvalidVarQueryError
# app/main.py                             # MODIFIED — one handler for InvalidVarQueryError

tests/
├── unit/
│   ├── test_var_backtest_stats.py        # NEW — Kupiec/Christoffersen/CC/zone/stability/
│   │                                     #   rolling, against hand-worked values
│   ├── test_var_window.py                # NEW — resolve_window() defaulting/validation,
│   │                                     #   asserts it never calls read_full_df
│   ├── test_var_series_service.py        # NEW
│   ├── test_var_backtest_service.py      # NEW
│   ├── test_var_methods_service.py       # NEW
│   └── test_risk_var_series_openapi.py   # NEW — schema presence and links
├── features/
│   └── var_series_backtest_api.feature   # NEW — User Stories 1–4
└── steps/
    └── var_series_backtest_api_steps.py  # NEW — seeds estimates.csv/outcomes.csv directly
                                          #   via VarRepository.commit(), no run execution
```

**Structure Decision**: Existing single web-service project; this feature adds to the
existing `app/services/var/` package and `risk_var.py` router rather than creating new
top-level packages, since it is a thin read layer over feature 012's store and shares its
settings, repository and models package. `var_series.py` is a separate models module
(not added to `var.py`) because `var.py`'s types describe the run/status write-side
resource; the series/backtest/methods types describe this feature's distinct read-side
resources, and keeping them apart matches how `models/risk.py` is already separate from
`models/var.py`.

## Implementation Notes (for /speckit-tasks)

1. **Order**: `config.py` (`headline_lookback`) → `exceptions.py`
   (`InvalidVarQueryError`) → `backtest.py` (pure, test-first against the proposal's
   §4.3 formulas and the spec's hand-worked scenarios) → `var_window.py` → model module
   → `var_series_service.py` → `var_backtest_service.py` → `var_methods_service.py` →
   router endpoints + `main.py` handler → BDD → README update.
2. **`var_window.py` must not read the ladder file.** It depends only on
   `AccountsService.get_summary()` (metadata) and `TimeseriesDateResolver`, exactly as
   `VarStatusService` already does — this is what keeps SC-004's 2-second budget
   achievable, since reading `estimates.csv`/`outcomes.csv` is cheap but
   `LadderRepository.read_full_df()` is not.
3. **Quality/pending handling is different between the two endpoints** (Assumptions):
   the series endpoint includes every stored date regardless of quality (nulling only the
   fields that have no value); the backtest endpoint always drops `insufficient` and
   pending-outcome dates from its observation set before any `min_quality` filter is
   applied.
4. **Do not** modify `VarRepository`, `engine.py`, `var_run_service.py`,
   `var_status_service.py`, or any existing response shape. This feature only adds new
   files plus the two small, additive changes to `config.py` and `exceptions.py`/`main.py`.
5. **README**: add the three endpoints to the capability table; document
   `var.headline_lookback` alongside the existing `var:` config block.

## Complexity Tracking

*None — no Constitution Check violations.*
