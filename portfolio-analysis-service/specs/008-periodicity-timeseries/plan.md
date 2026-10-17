# Implementation Plan: Periodicity Parameter for Account & Position Time Series

**Branch**: `008-periodicity-timeseries` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-periodicity-timeseries/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add an optional `periodicity` query parameter (`day` | `week` | `month` | `quarter` | `annual`,
defaulting to `day`) to `GET /v1/accounts/{account_name}/timeseries` and
`GET /v1/accounts/{account_name}/position`, and echo the applied value back as a new
`periodicity` response field.

The whole feature is a **pure post-processing step on the already-expanded daily frame**. Both
services already produce a business-day-complete, forward-filled `DataFrame` immediately before
they build response entries (`TimeSeriesService` after its capital/market-value merge and `pnl`
computation; `PositionTimeSeriesService` after each position's `expand_business_days` call and
`pnl` computation). Aggregation slots in exactly there: label each row with its calendar period
via `pd.Series.dt.to_period()`, keep the **last row** of each period, and re-date that row to the
period's start business day (clamped to the resolved start for the first window). Nothing before
that point changes — date defaulting, business-day adjustment, source-coverage validation,
forward-fill and the attribute registries are all untouched, which is what makes FR-016 and the
backward-compatibility requirements (FR-002, FR-003, FR-012) cheap to guarantee.

Two behaviours are worth calling out because they fall out of the "keep the last **row**" choice
rather than needing extra code. Taking a whole row (not a per-column last-valid value) satisfies
FR-008's same-source-date consistency for free. And because a window's reported date is derived
only from the calendar period plus the resolved start — never from the data in the frame — window
dates are identical across positions, so a client can align per-position series with the
account-level series without any extra work.

Validation deliberately does **not** use a FastAPI `Enum`-typed parameter. A typed enum would make
FastAPI emit its own `RequestValidationError` body, which is not RFC 7807 and would violate
Constitution V; adding a global `RequestValidationError` handler would change error bodies on every
existing endpoint, which FR-016 forbids. Instead the parameter stays `str | None` with
`json_schema_extra={"enum": [...]}` (verified to surface the enum in `/openapi.json`, satisfying
FR-017), and a new `resolve_periodicity()` validator raises a new `UnsupportedPeriodicityError`
that gets its own RFC 7807 handler — exactly the pattern `UnsupportedAttributeError` already
follows.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python = ">=3.11"`, `ruff target-version = py311`)
**Primary Dependencies**: FastAPI 0.139.0, pandas 3.0.3, Pydantic 2.13.4, structlog 26.1.0 —
all already in use. **No new dependencies.** Period bucketing uses `pandas` only, via
`Series.dt.to_period()` and `pd.bdate_range()`, both already used elsewhere in the codebase
(`business_day_expansion.py`, `timeseries_date_resolver.py`)
**Storage**: Filesystem — reads existing per-account `ladder.xlsx`/`capital.xlsx` + `meta.json`
through the existing `LadderRepository` / `CapitalRepository`. **This feature persists nothing**
and adds no new stored column; aggregation is entirely read-time
**Testing**: `pytest` unit tests in `tests/unit/`, `pytest-bdd` Gherkin scenarios in
`tests/features/*.feature` + `tests/steps/*_steps.py` (markers `us1`, `us2`, `us3`, `validation`
already declared in `pyproject.toml`)
**Target Platform**: Locally hosted service (uvicorn), Windows or Linux
**Project Type**: Single web-service project (existing `app/` layout; no frontend component)
**Performance Goals**: Strictly cheaper than the status quo — one `to_period()` vectorized label
pass plus one `groupby(...).tail(1)` over a frame that has already been built, then **fewer**
entries to serialise (a verified 10-year daily series of 2,608 rows collapses to 10 annual / 40
quarterly / 120 monthly / 522 weekly rows). No new I/O and no new external calls
**Constraints**: MUST NOT alter any existing response field, error response, or validation rule
(FR-012, FR-016); MUST NOT add a global `RequestValidationError` handler (would change existing
endpoints' error bodies); MUST reuse `TimeseriesDateResolver`, `AccountsService`,
`expand_business_days` and both attribute registries unchanged; aggregation MUST be a pure
function so it is unit-testable without repositories or HTTP
**Scale/Scope**: Two existing endpoints gain one optional parameter and one response field; two
new modules (~120 lines total), one new exception + handler. No new endpoint, no new attribute,
no schema migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: Gherkin scenarios are already written in `spec.md` (User Stories 1–3) and
  will land as `tests/features/timeseries_periodicity.feature` + step definitions. Unit tests for
  the pure aggregator (`test_periodicity_aggregation.py`) and the validator
  (`test_periodicity_validator.py`) precede every implementation task in Phase 2, and the
  backward-compatibility assertions (omitted param ≡ `periodicity=day`) are written as tests
  before the parameter exists.
- [x] **II. SOLID**: The new behaviour is a **separate single-responsibility module**
  (`periodicity_aggregation.py` — bucket and select, nothing else) and a separate validator
  (`validators/periodicity.py` — parse and reject, nothing else); the `Periodicity` vocabulary is
  a standalone value object in `app/models/`. The two orchestrating services gain one
  defaulted parameter and one delegating call each — the aggregation rules themselves are closed
  to modification and extensible by adding an enum member plus an alias entry (Open/Closed).
  Services depend on the pure function's signature, not on pandas period mechanics
  (Dependency Inversion); the aggregator takes a `DataFrame` and returns a `DataFrame`, so it
  needs no repository, no HTTP, and no account context (Interface Segregation).
- [x] **III. Type Safety**: Both new modules carry full annotations and Google-style docstrings,
  pass `mypy --strict`, and are `ruff check` / `ruff format` clean. The new response field is a
  Pydantic field on the existing `TimeSeriesResponse` / `PositionTimeSeriesResponse` models
  (external boundary), typed as the `Periodicity` enum rather than a bare `str`.
- [x] **IV. Observability**: The existing `timeseries_request` and `position_timeseries_request`
  structlog events gain `periodicity` and (when aggregating) `window_count` fields, so a log line
  states which rule was applied and how much the series was reduced. `resolve_periodicity()`
  failures log a `warning` through the new handler, matching `unsupported_attribute`.
- [x] **V. RESTful/OpenAPI**: No new resource — two existing GET resources gain one optional query
  parameter. `contracts/openapi.yaml` documents the parameter, the response field and the new
  error. The parameter's allowed values appear as a machine-readable `enum` in `/openapi.json`
  (verified in Phase 0). Existing `_links` are unchanged. The new error response is RFC 7807
  `application/problem+json` via a new handler registered in `app/main.py`, consistent with the
  other 14 handlers.
- [x] **No principle violations**: Complexity Tracking table left empty — no deviations.

**Post-Phase-1 re-check (2026-09-22)**: re-evaluated after `research.md`, `data-model.md`,
`contracts/openapi.yaml` and `quickstart.md` were written. All six gates still pass and the design
did not grow: still three new files, seven modified, zero new dependencies, zero persisted schema
changes. Two gates were *strengthened* by Phase 0's empirical checks rather than weakened — gate V
(the `json_schema_extra` enum was confirmed to surface in the generated `/openapi.json`, so FR-017
holds without an enum-typed parameter that would have broken RFC 7807 compliance) and gate II (the
aggregator's signature was confirmed to need no repository, account or HTTP context, so it is
unit-testable as a pure function). No Complexity Tracking entries were required.

## Project Structure

### Documentation (this feature)

```text
specs/008-periodicity-timeseries/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
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
│   ├── periodicity.py                  # NEW — Periodicity(str, Enum) value object +
│   │                                   #   SUPPORTED_PERIODICITY_VALUES; imported by both
│   │                                   #   response models, the validator and the aggregator
│   ├── timeseries.py                   # MODIFIED — TimeSeriesResponse gains
│   │                                   #   `periodicity: Periodicity = Periodicity.DAY`
│   └── position_timeseries.py          # MODIFIED — PositionTimeSeriesResponse gains the
│                                       #   same defaulted field
├── services/
│   ├── periodicity_aggregation.py      # NEW — aggregate_last_observation(df, periodicity,
│   │                                   #   resolved_start) -> DataFrame; pure, no I/O
│   ├── timeseries_service.py           # MODIFIED — get_series() gains
│   │                                   #   `periodicity: Periodicity = Periodicity.DAY`;
│   │                                   #   aggregates after the pnl step, before entries
│   ├── position_timeseries_service.py  # MODIFIED — get_series() gains the same parameter;
│   │                                   #   aggregates inside the per-position loop
│   ├── business_day_expansion.py       # unchanged — reused as-is
│   ├── timeseries_date_resolver.py     # unchanged — reused as-is
│   ├── accounts_service.py             # unchanged — reused as-is
│   ├── timeseries_attributes.py        # unchanged
│   └── position_attributes.py          # unchanged
├── validators/
│   └── periodicity.py                  # NEW — resolve_periodicity(raw: str | None)
│                                       #   -> Periodicity; raises UnsupportedPeriodicityError
├── api/
│   ├── timeseries.py                   # MODIFIED — new `periodicity` query param, resolved
│   │                                   #   then passed to the service
│   └── position_timeseries.py          # MODIFIED — same change on the /position route only
├── exceptions.py                       # MODIFIED — NEW UnsupportedPeriodicityError
└── main.py                             # MODIFIED — NEW RFC 7807 handler (422,
                                        #   "unsupported-periodicity")

tests/
├── features/
│   └── timeseries_periodicity.feature  # NEW — US1/US2/US3 Gherkin scenarios from spec.md
├── steps/
│   └── timeseries_periodicity_steps.py # NEW — step definitions for the above
└── unit/
    ├── test_periodicity_aggregation.py # NEW — window alignment, counts, first-window clamp,
    │                                   #   last-row selection, empty-window omission,
    │                                   #   cross-position date uniformity
    └── test_periodicity_validator.py   # NEW — default, each valid token, rejection cases
```

**Structure Decision**: The existing single-project `app/` layout is retained
(`models/` → `validators/` → `services/` → `api/`, with `repositories/` beneath). The feature adds
three files and modifies seven, all in their established layers. `Periodicity` lives in `models/`
rather than `services/` so that the response models can type the new field against it without a
model→service import (the codebase's import direction is services→models). The aggregator lives in
`services/` beside `business_day_expansion.py`, which it deliberately mirrors: a pure
`DataFrame`-in/`DataFrame`-out calendar helper with no repository or account awareness. The
validator lives in `validators/` and is invoked from the API layer, mirroring how
`validate_account_name` is called from both routers today, so the services receive an
already-typed `Periodicity`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally empty.
