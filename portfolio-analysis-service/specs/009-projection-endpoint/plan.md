# Implementation Plan: Account Projection Endpoint

**Branch**: `020-projection-endpoint` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/009-projection-endpoint/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add `GET /v1/accounts/{account_name}/projection`, implementing the contract already pinned by
`portfolio-browser`'s feature 022. The response reuses `PositionTimeSeriesResponse` unmodified
(its `position` field repurposed as a series label); a new `ProjectionService` orchestrates
validation, start-date resolution, a historical `market_value` series (reusing
`TimeSeriesService`'s own account-level aggregation), and one projected series per requested
return — each computed as `daily_rate = (1 + annualized_return) ** (1/260) - 1` compounded daily
from the account's actual market value on the resolved start date, using the account's own
existing `compute_performance_measures()` output. Periodicity bucketing reuses
`aggregate_last_observation()` unmodified, once per series.

Three corrections to the originally-pinned contract are made here, all recorded in detail in
`research.md`:

1. **Return names reuse `performance_attributes.py`'s exact strings** (`"ITD (Ann.)"`, `"1Y"`,
   `"3Y"`, `"5Y"`) rather than the lowercase wire codes `portfolio-browser`'s own research.md
   guessed at before this service's real measure names were available to it (`research.md` #2).
2. **Start-date defaulting is new, small, local logic — not a reuse of
   `TimeseriesDateResolver`** — that class defaults toward the *earliest* date and caps at
   *today*; this endpoint needs the opposite on both counts, so forcing its reuse would corrupt
   its own documented contract rather than save real code (`research.md` #3).
3. **The projection formula's de-annualization step (2026-09-24, post-implementation)**: the
   originally-pinned `daily_rate = annualized_return * sqrt(260)` was implemented exactly as
   specified, then found in production use to produce grossly wrong values — `sqrt(260)` scales
   volatility, not returns. Fixed to the mathematically correct 260th root,
   `(1 + annualized_return) ** (1/260) - 1`, the exact inverse of this service's own
   `itd_ann = (1 + itd) ** (260/elapsed) - 1` annualization (`research.md` #5).

## Technical Context

**Language/Version**: Python 3.13 (matching the installed `.venv`; `pyproject.toml` targets
py311+ compatible syntax throughout the existing codebase)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas, structlog — all already in use. **No new
dependencies.**
**Storage**: Parquet-cached ladder/capital files via the existing `LadderRepository` — read-only
for this feature; no new storage, no new ingestion path.
**Testing**: `pytest` unit tests (`tests/unit/`), `pytest-bdd` Gherkin scenarios
(`tests/features/*.feature` + `tests/steps/*.py`), both already the established pattern for
every prior feature in this repository.
**Target Platform**: Locally hosted FastAPI service (`uvicorn app.main:app`), consumed by
`portfolio-browser` over HTTP — this plan covers this service only; the consumer side
(`portfolio-browser`'s feature 022) is already built against this contract via a fake client and
is out of scope here.
**Performance Goals**: No new performance requirement beyond what every other periodicity-aware
endpoint already meets — a combined historical-plus-projected span at a coarse periodicity
reduces to the same order of magnitude of points `aggregate_last_observation()` already produces
elsewhere (roughly one point per calendar period per series, not one point per business day).
**Constraints**: MUST NOT introduce a second, parallel definition of any of the four return
measures — `compute_performance_measures()` is the single source of truth (Principle II); MUST
NOT alter `TimeSeriesService`, `PositionTimeSeriesService`, `PerformanceService`, or
`periodicity_aggregation.py` — every one of them is reused read-only; MUST follow the existing
RFC 7807 error convention exactly, including reusing existing exception classes wherever the
underlying condition is already handled elsewhere in this service (only one new exception class
is introduced — see `research.md` #7).
**Scale/Scope**: One new endpoint, one new service class, one new small validation module, one
new exception class + handler. No change to any existing endpoint's behavior, request shape, or
response shape.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: `tests/features/retrieve_projection.feature` (Gherkin, transcribing
  spec.md's three user stories) plus `tests/unit/test_projection_service.py` and
  `tests/unit/test_projection_returns.py` are written before their corresponding
  implementation, per the task breakdown's ordering — mirroring `test_performance_service.py`'s
  own Red-Green-Refactor precedent for this exact layering pattern.
- [x] **II. SOLID**: Single responsibility preserved — `ProjectionService` owns orchestration
  only; it reuses `TimeSeriesService`'s aggregation logic, `PerformanceService`'s underlying
  measure computation (`compute_performance_measures`), and `periodicity_aggregation.py`'s
  bucketing, rather than reimplementing any of them. Open/closed: none of those three existing
  modules is modified — `ProjectionService` extends by composition. Dependency inversion:
  `ProjectionService` depends on `LadderRepository`/`AccountsService`, the same abstractions
  every sibling service already depends on, injected the same way via `app/api/dependencies.py`.
- [x] **III. Type Safety**: Full type annotations throughout; `mypy --strict` and `ruff check`
  must pass clean, matching every existing module; `PositionTimeSeriesResponse` (already a
  Pydantic model) is the external boundary, reused rather than duplicated.
- [x] **IV. Observability**: `ProjectionService.get_projection()` logs a single structured
  `projection_request` event (account_name, resolved start/projection_date, periodicity,
  requested vs. computed returns, row_count), matching the `*_request` logging convention every
  sibling `*Service` already follows; the existing request-logging middleware and correlation-ID
  binding apply automatically, with no new code needed.
- [x] **V. RESTful/OpenAPI**: `/v1/accounts/{account_name}/projection` is a noun-resource path
  under the existing `/v1` prefix, `GET`-only; FastAPI's own OpenAPI generation picks up the new
  route automatically from its `summary`/`responses` kwargs (no hand-maintained OpenAPI file
  exists in this repo, matching every other endpoint); `_links` (`self`, `accounts`) follows the
  existing HATEOAS convention; every error path returns RFC 7807 `application/problem+json`,
  reusing five existing exception+handler pairs and adding exactly one new pair
  (`InvalidProjectionRangeError`, `research.md` #7).
- [x] **No principle violations**: Complexity Tracking table left empty — no deviations.

**Post-Phase-1 re-check (2026-09-23)**: re-evaluated after `research.md`, `data-model.md`,
`contracts/projection-api.md`, and `quickstart.md` were written. All five gates still pass. Two
decisions were *corrected* during Phase 0 relative to the originally-pinned contract/implementation
hint (return-name strings; start-date resolution not reusing `TimeseriesDateResolver`) — both
corrections *strengthen* Principle II rather than weaken it, since the alternative in each case
was either duplicating a naming scheme that already exists elsewhere (return names) or bending an
existing class past what its own tests and docstring say it does (date resolution). No Complexity
Tracking entries were required.

## Project Structure

### Documentation (this feature)

```text
specs/009-projection-endpoint/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── projection-api.md   # Finalized endpoint contract (Phase 1 output)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root of `portfolio-analysis-service/`)

```text
app/
├── exceptions.py                       # MODIFIED — NEW InvalidProjectionRangeError
├── main.py                             # MODIFIED — register the new router; add the new
│                                       #   exception's handler alongside the existing five
├── api/
│   ├── dependencies.py                 # unchanged — get_ladder_repository reused as-is
│   └── projection.py                   # NEW — router, request parsing, _get_projection_
│                                       #   service() dependency provider, mirroring
│                                       #   performance.py's structure exactly
├── services/
│   ├── projection_service.py           # NEW — ProjectionService.get_projection():
│                                       #   validation → start resolution → historical build
│                                       #   → per-return projected build → response assembly
│   ├── projection_returns.py           # NEW — SUPPORTED_PROJECTION_RETURNS,
│                                       #   validate_returns() (research.md #2)
│   ├── performance_metrics.py          # unchanged — compute_performance_measures() reused
│   ├── daily_portfolio_return.py       # unchanged — compute_daily_portfolio_return() reused
│   ├── timeseries_service.py           # unchanged — its market_value aggregation pattern is
│                                       #   mirrored, not imported (research.md #4); no shared
│                                       #   code extraction needed for a two-line groupby+sum
│   ├── periodicity_aggregation.py      # unchanged — aggregate_last_observation() reused as-is
│   ├── accounts_service.py             # unchanged — get_summary() reused as-is
│   └── business_day_expansion.py       # unchanged — expand_business_days() reused as-is
├── validators/
│   ├── account_name.py                 # unchanged — validate_account_name() reused as-is
│   └── periodicity.py                  # unchanged — resolve_periodicity() reused as-is
└── models/
    └── position_timeseries.py          # unchanged — PositionTimeSeriesResponse reused as-is

tests/
├── features/
│   └── retrieve_projection.feature     # NEW — the spec's three user stories, Gherkin
├── steps/
│   └── retrieve_projection_steps.py    # NEW — step definitions, real FastAPI TestClient
│                                       #   against a fixture-ingested account (matching
│                                       #   retrieve_performance_steps.py's own pattern)
└── unit/
    ├── test_projection_service.py      # NEW — orchestration, date resolution, silent-omission
    │                                   #   rule, formula correctness, every error path
    └── test_projection_returns.py      # NEW — validate_returns(): empty list accepted, each
                                        #   supported name accepted, "ITD" itself rejected,
                                        #   an unknown name rejected
```

**Structure Decision**: Single-project FastAPI layout unchanged
(`app/models/` → `app/repositories/` → `app/services/` → `app/validators/` → `app/api/`). This
feature adds one new service, one new small validator module, one new router, and one new
exception — following the `PerformanceService`/`performance.py` pair as its direct structural
template (both have no `date_resolver`/`capital_repo` dependency, both need only
`ladder_repo`+`accounts_service`), rather than `PositionTimeSeriesService`/`position_timeseries.py`
(which needs `positions_service` for position enumeration — this endpoint has no equivalent
concept, since "which returns to project" is a fixed, validated set, not an account-specific
enumeration).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally empty.
