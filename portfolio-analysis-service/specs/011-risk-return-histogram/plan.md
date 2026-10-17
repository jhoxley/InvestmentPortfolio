# Implementation Plan: Risk Endpoints — Daily Return Histogram

**Branch**: `011-risk-return-histogram` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-risk-return-histogram/spec.md`

## Summary

Add a new "risk" API group whose first endpoint,
`GET /v1/accounts/{account_name}/risk/return-histogram?start=&end=`, returns a sparse,
ascending histogram of the account's portfolio-level daily returns (rounded to integer basis
points) plus a statistics block (mean, median, mode, sample standard deviation with 1/2/3σ
multiples and band edges, count, skewness, excess kurtosis, min, max).

The daily return series is exactly the one the performance endpoints use
(`compute_daily_portfolio_return`). To share, not copy, the surrounding orchestration — account
existence checks, source-missing errors, date resolution, ladder read, daily-return aggregation —
that logic is extracted from `PerformanceService` into a small `DailyReturnSeriesLoader`, which
both `PerformanceService` and the new `RiskService` depend on. Bucketing and statistics are pure
functions (`return_histogram.py`) over the windowed series, using vectorised pandas/numpy with no
new dependencies.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI 0.139.x, pandas 3.0.x, numpy 2.5.x, Pydantic 2.x, structlog,
pytest + pytest-bdd (dev) — all already pinned; no new dependencies
**Storage**: Filesystem — reads the existing per-account ladder via `LadderRepository`; no new
persistence
**Testing**: `pytest` unit tests (`tests/unit/`), `pytest-bdd` Gherkin scenarios
(`tests/features/*.feature` + `tests/steps/*_steps.py`)
**Target Platform**: Locally hosted service (uvicorn), Linux or Windows
**Project Type**: Single web-service project (existing `app/` layout)
**Performance Goals**: Up to ~10 years (~2,600 business days) per request in well under 2 s (SC-004);
one ladder read plus O(n) vectorised operations
**Constraints**: MUST reuse `compute_daily_portfolio_return`, `TimeseriesDateResolver`,
`AccountsService` (FR-003, FR-002); no new exception types or handlers; existing performance
behaviour MUST NOT change (regression-guarded by existing performance tests)
**Scale/Scope**: One new endpoint; one new router; one small refactor of `PerformanceService`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: Gherkin scenarios exist in spec.md (User Stories 1–4); tasks will place
  unit tests (`test_return_histogram.py`, `test_risk_service.py`,
  `test_daily_return_series_loader.py`) and BDD steps before implementation. The
  `PerformanceService` refactor is guarded by the existing `test_performance_service.py` and
  `retrieve_performance.feature`, which must stay green throughout.
- [x] **II. SOLID**: Single-responsibility modules — loader (account/date/series acquisition),
  pure histogram/statistics functions, `RiskService` orchestrator, router. Extracting the loader
  is a refactor to remove duplication; both services depend on it by injection (Dependency
  Inversion). New risk measures later extend the risk group without editing the loader.
- [x] **III. Type Safety**: Full annotations, docstrings, `mypy --strict`, `ruff check`/`format`
  clean. Pydantic models at the API boundary.
- [x] **IV. Observability**: `RiskService` emits a structured `return_histogram_request` event
  (account, resolved range, observation count, bucket count); the loader logs via structlog like
  existing services. Existing request-logging middleware covers the HTTP cycle.
- [x] **V. RESTful/OpenAPI**: GET-only noun resource under `/v1/`; `contracts/openapi.yaml`
  documents it; `_links` (`self`, `accounts`) in the response; errors reuse existing RFC 7807
  handlers (`AccountNotFoundError`, `MissingRequiredSourceError`, `FutureEndDateError`,
  `InvalidDateRangeError`, `InvalidAccountNameError`).
- [x] **No principle violations**: Complexity Tracking is empty.

**Post-design re-check**: Design (see data-model.md, contracts/) introduces no deviations; all gates
still pass.

## Project Structure

### Documentation (this feature)

```text
specs/011-risk-return-histogram/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── models/
│   └── risk.py                          # NEW — ReturnHistogramResponse, HistogramStatistics,
│                                        #   StdDevBand
├── services/
│   ├── daily_return_series_loader.py    # NEW — extracted from PerformanceService: validates
│   │                                    #   account/source, resolves dates, reads ladder,
│   │                                    #   returns full daily-return series + resolved range
│   ├── return_histogram.py              # NEW — pure functions: round_half_away_from_zero(),
│   │                                    #   to_basis_points(), build_histogram(),
│   │                                    #   compute_statistics()
│   ├── risk_service.py                  # NEW — RiskService.get_return_histogram()
│   ├── performance_service.py           # MODIFIED — delegates to DailyReturnSeriesLoader
│   │                                    #   (behaviour unchanged)
│   ├── daily_portfolio_return.py        # unchanged — reused
│   ├── timeseries_date_resolver.py      # unchanged — reused
│   └── accounts_service.py              # unchanged — reused
├── api/
│   └── risk.py                          # NEW — GET /accounts/{account_name}/risk/return-histogram
└── main.py                              # MODIFIED — include risk.router

tests/
├── unit/
│   ├── test_daily_return_series_loader.py   # NEW
│   ├── test_return_histogram.py             # NEW — bucketing, rounding, sort, stats, nulls
│   └── test_risk_service.py                 # NEW — orchestration, errors, window slicing
├── features/
│   └── return_histogram.feature             # NEW — User Stories 1–4
└── steps/
    └── return_histogram_steps.py            # NEW
```

**Structure Decision**: Existing single web-service project. Additive modules mirror the
performance feature's shape (model / service / router). The only edits to existing files are the
behaviour-preserving `PerformanceService` refactor and router registration in `main.py`.

## Complexity Tracking

*No Constitution Check violations — table intentionally left empty.*
