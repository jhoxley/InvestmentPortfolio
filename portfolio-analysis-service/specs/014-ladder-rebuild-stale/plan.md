# Implementation Plan: On-Demand Ladder Rebuild for Stale Requests

**Branch**: `014-ladder-rebuild-stale` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-ladder-rebuild-stale/spec.md`

## Summary

Every date-range-bearing GET endpoint that reads the position ladder or capital ledger
(`timeseries`, `position`, `positions`, `performance`, `risk/return-histogram`) currently
flat-fills forward from the last persisted row with no awareness of "today" — a request whose
range extends weeks past the last ingestion returns one repeated stale value instead of real
market-priced data. This feature adds a shared staleness check, invoked by each of those read
services right after date resolution: if the resolved end date is later than the resource's
last-ingested-or-rebuilt date (`AccountMeta.to_date` / `CapitalMeta.to_date`), the service
synchronously rebuilds the missing period — reusing `LadderExpander`'s existing
hold-positions-constant forward-fill plus a fresh `PricingEnrichmentService`/
`ReturnsEnrichmentService` pass for the position ladder, and a plain persisted
`expand_business_days()` extension for the capital ledger (which has no pricing dependency) —
capped at the prior business day, and persists the result tagged with a new `provenance` column
so a later ledger ingestion that overlaps a projected span can correctly supersede it. Concurrent
requests for the same gap are serialised by an in-process per-(account, resource) lock, mirroring
the existing `ThreadRunScheduler` pattern used for VaR runs.

## Technical Context

**Language/Version**: Python 3.11 (runtime); mypy checked against 3.12 stub syntax (existing project convention, unrelated to this feature)
**Primary Dependencies**: FastAPI 0.115, Pydantic 2.x, pandas 2.x, httpx (market-data-web-service client), structlog, openpyxl
**Storage**: Local filesystem — per-account `ladder.xlsx`/`meta.json` and `capital.xlsx`/`capital_meta.json` under the configured data directory; no database
**Testing**: pytest + pytest-bdd (Gherkin features under `tests/features/`, step defs under `tests/steps/`), unit tests under `tests/unit/`
**Target Platform**: Locally hosted single-process API server (Linux or Windows)
**Project Type**: web-service (single FastAPI application, no separate frontend)
**Performance Goals**: A stale request's rebuild runs synchronously within the triggering HTTP call; no numeric SLA was specified, and none is required by the spec — the rebuild's cost is bounded by the market-data-service's own response time for the gap's date range, which this feature does not attempt to optimise beyond "exactly once per gap" (FR-004/FR-005)
**Constraints**: Rebuild target end date MUST NOT exceed the prior business day relative to today (FR-003); exactly one rebuild per (account, resource, gap) under concurrency (FR-005); total market-data unavailability MUST fall back silently with no partial persistence (FR-013)
**Scale/Scope**: Two known accounts in current data (`HL-ISA`, `HL-SIPP`); single-process deployment — no evidence of horizontal scaling, so an in-process lock is sufficient (see research.md R6)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: BDD Gherkin scenarios already defined in spec.md for all three user stories; tasks.md (next command) will order unit/BDD test tasks before their implementation tasks.
- [x] **II. SOLID**: New `StalenessGate`/rebuild orchestration is a separate service from `LadderExpander`, `PricingEnrichmentService`, `ReturnsEnrichmentService`, and the repositories — each keeps its existing single responsibility; rebuild composes them rather than modifying their contracts (research.md R1, R2, R7).
- [x] **III. Type Safety**: New/changed fields (`provenance`, `rebuilt_at`, nullable attribute values) will carry full type annotations and Pydantic models at the API boundary; `mypy --strict` and `ruff check` must pass as part of task completion.
- [x] **IV. Observability**: Rebuild start/complete, lock-wait, partial-unavailability, and total-unavailability-fallback events will be logged as structured JSON via the existing `structlog` pattern used throughout `app/services/`.
- [x] **V. RESTful/OpenAPI**: No new endpoints, no new verbs; existing resources/paths unchanged. OpenAPI descriptions updated per contracts/rebuild-trigger-delta.md. Existing RFC 7807 error shapes and `_links` are unchanged by this feature.
- [x] **No principle violations**: No deviations require Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/014-ladder-rebuild-stale/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── rebuild-trigger-delta.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
app/
├── api/
│   ├── timeseries.py             # unchanged routing; docstring/description update only
│   ├── position_timeseries.py    # unchanged routing; docstring/description update only
│   ├── performance.py            # unchanged routing; docstring/description update only
│   ├── risk.py                   # unchanged routing; docstring/description update only
│   └── ladder.py                  # ingestion endpoint gains the supersession branch (R5)
├── services/
│   ├── rebuild/                   # NEW package
│   │   ├── staleness_gate.py       # NEW: decides whether a rebuild is needed, computes the gap
│   │   ├── ladder_rebuild_service.py   # NEW: position-ladder rebuild (expand+price+returns, persist)
│   │   ├── capital_rebuild_service.py  # NEW: capital-ledger rebuild (expand+persist, no pricing)
│   │   └── rebuild_lock_registry.py    # NEW: per-(account, resource) threading.Lock registry
│   ├── ladder_expander.py          # gains an explicit end_date parameter (currently hardcoded T-2)
│   ├── timeseries_service.py       # calls StalenessGate before read_full_df/read_df
│   ├── position_timeseries_service.py  # same
│   ├── performance_service.py      # same
│   ├── daily_return_series_loader.py   # same (backs risk/return-histogram)
│   └── ingestion_service.py        # gains the R5 supersession branch for projected-span overlap
├── repositories/
│   ├── ladder_repository.py        # AccountMeta gains rebuilt_at; ladder rows gain provenance
│   └── capital_repository.py       # CapitalMeta gains rebuilt_at; capital rows gain provenance
└── models/
    ├── timeseries.py               # TimeSeriesEntry attribute values become nullable
    ├── position_timeseries.py      # analogous nullability
    └── performance.py              # analogous nullability

tests/
├── features/
│   └── 014-ladder-rebuild-stale.feature   # NEW: Gherkin scenarios from spec.md
├── steps/
│   └── test_014_ladder_rebuild_stale_steps.py  # NEW
└── unit/
    ├── test_staleness_gate.py              # NEW
    ├── test_ladder_rebuild_service.py       # NEW
    ├── test_capital_rebuild_service.py      # NEW
    ├── test_rebuild_lock_registry.py        # NEW
    └── test_ingestion_service_supersession.py  # NEW (extends existing ingestion tests)
```

**Structure Decision**: Single existing FastAPI project (`app/`). This feature adds one new
`app/services/rebuild/` package for the new orchestration logic, extends three existing
repositories/models for the new fields, and makes small additive changes to each affected read
service and to `IngestionService`. No new top-level project, no new router module, no new
persisted file format (same XLSX + JSON meta convention, extended with one new column/field).

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
