# Implementation Plan: Account Performance Retrieval Endpoints

**Branch**: `007-performance-endpoints` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-performance-endpoints/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a new "performance" API group mirroring the existing account time series endpoint's
request/response shape: `GET /v1/accounts/{account_name}/performance` returns `ITD`,
`ITD (Ann.)`, `1Y`, `3Y`, and `5Y` return measures per business day, and
`GET /v1/performance/attributes` describes them. Every measure is derived at request time from
the account's already-persisted `weighted_position_return` (feature 006) — summed per date to
form a daily portfolio return, then compounded (expanding for ITD/ITD (Ann.), rolling 260/780/1300
business days for 1Y/3Y/5Y) using vectorized pandas. Because the existing `LadderRepository`
already reads an account's entire stored history unconditionally, the "look back further than the
requested window" requirement (User Story 3) requires no special-cased logic — every measure is
computed over the full history first and sliced to the requested window last. A measure without
enough preceding history naturally computes to `NaN` (pandas `rolling`'s default `min_periods`)
and is dropped from that date's entry, satisfying the resolved clarification. Date defaulting and
account/source-missing errors reuse the existing `TimeseriesDateResolver`, `AccountsService`, and
exception vocabulary unchanged.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI 0.115.x, pandas (>=2.0, pinned via `requirements.txt`),
Pydantic 2.x, structlog, pytest + pytest-bdd (dev) — all already in use, no new dependencies
**Storage**: Filesystem — reads the existing `ladder.xlsx` + `meta.json` per account via
`LadderRepository` (feature 001/002); this feature introduces no new persisted storage of its own
**Testing**: `pytest` for unit tests (`tests/unit/`), `pytest-bdd` for Gherkin acceptance
scenarios (`tests/features/*.feature` + `tests/steps/*_steps.py`)
**Target Platform**: Locally hosted service (uvicorn), Linux or Windows
**Project Type**: Single web-service project (existing `app/` layout; no frontend/mobile
component)
**Performance Goals**: No new external calls are introduced (no market-data-service requests);
each request reads one account's full stored ladder into memory and computes five vectorized
pandas operations over it — the same order of cost as the existing time series endpoint's
`market_value` aggregation
**Constraints**: MUST reuse `TimeseriesDateResolver` and `AccountsService` unchanged (FR-004);
MUST NOT introduce a new ingestion-time persistence step (performance measures are computed at
read time only, per spec Assumptions); MUST NOT add new FastAPI exception handlers — all error
conditions map to already-registered exception types
**Scale/Scope**: Same order of magnitude as the existing ladder/time series features (per
account: a handful of sub-accounts × several years of business-day rows) — no new scale
dimension is introduced; two new endpoints, no changes to existing ones

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: Gherkin scenarios already defined in spec.md (User Stories 1–4); Phase 2
  tasks will add unit tests for the daily-return aggregation and performance-metric formulas, plus
  BDD step definitions, before any implementation task — mirroring feature 004/006's
  `test_timeseries_service.py` / `test_returns_enrichment_service.py` pattern.
- [x] **II. SOLID**: New, single-responsibility modules — a pure daily-portfolio-return
  aggregation function, a pure performance-metrics computation module, a `performance_attributes`
  registry (mirrors `timeseries_attributes.py`), and a `PerformanceService` orchestrator (mirrors
  `TimeSeriesService`) — added alongside existing services, not by modifying them.
  `TimeseriesDateResolver`/`AccountsService` are reused via dependency injection, not subclassed
  or edited (Open/Closed, Dependency Inversion).
- [x] **III. Type Safety**: New modules will carry full type annotations, pass `mypy --strict`,
  and be `ruff check`/`ruff format` clean, consistent with the rest of `app/services/`.
- [x] **IV. Observability**: `PerformanceService.get_performance()` will emit a structured
  `structlog` info-level event (account, requested measures, resolved date range, row count) on
  completion, mirroring `TimeSeriesService.get_series()`'s `timeseries_request` event.
- [x] **V. RESTful/OpenAPI**: New resources (`/accounts/{account_name}/performance`,
  `/performance/attributes`), GET-only, nouns-as-resources, `/v1/` prefix. `contracts/openapi.yaml`
  documents both. HATEOAS `_links` on both responses. All error responses reuse existing RFC 7807
  handlers already registered in `app/main.py` (`AccountNotFoundError`,
  `MissingRequiredSourceError`, `NoAttributesRequestedError`, `UnsupportedAttributeError`,
  `FutureEndDateError`, `InvalidDateRangeError`) — no new handler needed.
- [x] **No principle violations**: Complexity Tracking table left empty — no deviations.

## Project Structure

### Documentation (this feature)

```text
specs/007-performance-endpoints/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── models/
│   └── performance.py                  # NEW — PerformanceEntry, PerformanceResponse,
│                                        #   PerformanceAttributeDefinition,
│                                        #   PerformanceAttributeMetadataResponse
├── services/
│   ├── daily_portfolio_return.py       # NEW — aggregates a ladder DataFrame into one
│                                        #   sum(weighted_position_return) row per business day
│   ├── performance_metrics.py          # NEW — pure functions computing ITD, ITD (Ann.),
│                                        #   1Y, 3Y, 5Y series from a daily-return series
│   ├── performance_attributes.py       # NEW — ATTRIBUTE_DEFINITIONS, SUPPORTED_ATTRIBUTES,
│                                        #   validate_attributes() (mirrors
│                                        #   timeseries_attributes.py)
│   ├── performance_service.py          # NEW — PerformanceService orchestrator; reuses
│                                        #   TimeseriesDateResolver + AccountsService
│   ├── timeseries_date_resolver.py     # unchanged — reused as-is
│   ├── accounts_service.py             # unchanged — reused as-is
│   └── timeseries_attributes.py        # unchanged — sibling registry, not modified
├── repositories/
│   └── ladder_repository.py            # unchanged — read_full_df() already returns every
│                                        #   stored column, including weighted_position_return
├── api/
│   ├── performance.py                  # NEW — GET /accounts/{account_name}/performance,
│                                        #   GET /performance/attributes
│   └── dependencies.py                 # unchanged — get_ladder_repository() reused as-is
└── main.py                             # MODIFIED — import and app.include_router(performance.router)

tests/
├── unit/
│   ├── test_daily_portfolio_return.py     # NEW — User Story 1
│   ├── test_performance_metrics.py        # NEW — User Story 3 (formulas + look-back/NaN rules)
│   └── test_performance_service.py        # NEW — orchestration: date resolution reuse, error
│                                            #   handling, response shape (User Story 2)
├── features/
│   ├── retrieve_performance.feature       # NEW — User Stories 1–3
│   └── performance_attribute_metadata.feature  # NEW — User Story 4
└── steps/
    ├── retrieve_performance_steps.py            # NEW
    └── performance_attribute_metadata_steps.py  # NEW
```

**Structure Decision**: Single existing web-service project (`app/` + `tests/`), no new
top-level directories. This feature follows the same shape as feature 004/005 (new attribute-set
endpoint groups): one new attribute registry, one new orchestrating service, one new router, and
one new pair of response models — all additive. The only modification to an existing file is
`app/main.py` (registering the new router); no existing service, repository, or model is changed.

## Complexity Tracking

*No Constitution Check violations — table intentionally left empty.*
