# Implementation Plan: Projection Start Alignment

**Branch**: `010-projection-start-alignment` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/010-projection-start-alignment/spec.md`

## Summary

For a non-daily `periodicity`, each projected series currently begins with a row dated at the
resolved start date even when that date is mid-period. That row is the *clamped first window*
produced by `aggregate_last_observation()` (its window-start date is clamped up to
`resolved_start`), so it sits alongside the next genuine window-start row (e.g. 2026-09-22 then
2026-10-01). The fix is a small, local trim in `ProjectionService._build_projected_series`: when the
periodicity is not `DAY` and `resolved_start` is not itself the window-start business day of its
own period, drop the clamped first row. `aggregate_last_observation()`, the historical series, the
response model, and the compounding maths are untouched. The end-of-series rule (FR-009) is already
satisfied by existing windowing and is locked in with a regression test. See `research.md`.

## Technical Context

**Language/Version**: Python 3.13 (existing `.venv`)
**Primary Dependencies**: FastAPI, Pydantic v2, pandas, structlog — all existing. **No new dependencies.**
**Storage**: N/A (read-only use of the existing ladder repository)
**Testing**: `pytest` unit tests (`tests/unit/test_projection_service.py`), `pytest-bdd` scenarios
(`tests/features/retrieve_projection.feature` + `tests/steps/retrieve_projection_steps.py`)
**Target Platform**: Locally hosted FastAPI service consumed by `portfolio-browser`
**Project Type**: web-service
**Performance Goals**: No change — at most one row fewer per projected series
**Constraints**: MUST NOT modify `periodicity_aggregation.py` or any endpoint sharing it
(Time series, Position time series, Performance — all reuse it read-only); MUST NOT change
request parameters or the response schema; projected values on retained dates unchanged (FR-007)
**Scale/Scope**: One private method changed plus one small helper; tests and one contract note

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: New Gherkin scenarios (spec User Stories 1–2) added to `retrieve_projection.feature` and unit tests written and seen failing before the fix; existing tests asserting `projected_entries[0].date == resolved_start` for periodic cases updated first
- [x] **II. SOLID**: Trim logic stays in `ProjectionService` (the only consumer needing it); shared aggregation left closed to modification
- [x] **III. Type Safety**: Helper fully annotated with docstring; `ruff check`, `ruff format`, `mypy --strict` to pass; no new external boundary
- [x] **IV. Observability**: Existing `projection_request` log retained; no new business event
- [x] **V. RESTful/OpenAPI**: No endpoint, schema, `_links` or error-format change; OpenAPI description of the projected series gains one sentence (see `contracts/`)
- [x] **No principle violations**

Post-design re-check: unchanged — all gates still pass.

## Project Structure

### Documentation (this feature)

```text
specs/010-projection-start-alignment/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── projection-api-delta.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
app/
└── services/
    └── projection_service.py          # _build_projected_series: trim clamped first window

tests/
├── features/retrieve_projection.feature   # new scenarios
├── steps/retrieve_projection_steps.py     # new step defs
└── unit/test_projection_service.py        # new + adjusted unit tests
```

**Structure Decision**: Existing single FastAPI project layout; only `projection_service.py` and
its tests change.

## Complexity Tracking

No violations to justify.
