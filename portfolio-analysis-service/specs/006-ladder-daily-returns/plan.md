# Implementation Plan: Position & Portfolio-Weighted Daily Returns

**Branch**: `006-ladder-daily-returns` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-ladder-daily-returns/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

During position-ladder ingestion (`POST /v1/accounts/{account_name}/ladder`), compute two new
per-row metrics — `position_return` (price change plus per-share income, relative to the
previous day's price) and `weighted_position_return` (that return scaled by the sub-account's
*start-of-day*, i.e. previous-row, `portfolio_weight`) — and persist them alongside the existing
priced ladder columns so they can be retrieved later without recomputation. Technical approach:
add a new `ReturnsEnrichmentService`, chained into `IngestionService` immediately after the
existing `PricingEnrichmentService` step (feature 002), using vectorized pandas per-sub-account
`shift(1)` operations for the T-1 lookups. Expose both new columns as retrievable attributes on
the existing position time series endpoint by adding two entries to
`app/services/position_attributes.py`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI 0.115.x, pandas (>=2.0, pinned via `requirements.txt`),
Pydantic 2.x, structlog, pytest + pytest-bdd (dev) — all already in use, no new dependencies
**Storage**: Filesystem — one `ladder.xlsx` + `meta.json` per account under the configured data
directory (`LadderRepository`); no database
**Testing**: `pytest` for unit tests (`tests/unit/`), `pytest-bdd` for Gherkin acceptance
scenarios (`tests/features/*.feature` + `tests/steps/*_steps.py`)
**Target Platform**: Locally hosted service (uvicorn), Linux or Windows
**Project Type**: Single web-service project (existing `app/` layout; no frontend/mobile
component)
**Performance Goals**: No new external calls are introduced (unlike feature 002, this feature
makes zero market-data-service requests); added ingestion cost is a bounded, vectorized
per-sub-account pandas computation over rows already in memory — negligible relative to the
existing price-enrichment step's network calls
**Constraints**: MUST NOT issue additional market-data-service requests; MUST NOT change the
existing ingestion pipeline's idempotency/refresh semantics (feature 002's checksum-based
`created`/`refreshed` status contract is unchanged); MUST reuse the existing safe-division
pattern already established in `PricingEnrichmentService` for zero-denominator edge cases
**Scale/Scope**: Same order of magnitude as the existing ladder (per account: a handful of
sub-accounts × several years of business-day rows) — no new scale dimension is introduced

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: Gherkin scenarios already defined in spec.md (User Stories 1–4); Phase 2
  tasks will add unit tests for `ReturnsEnrichmentService` and BDD step definitions before any
  implementation task, mirroring feature 002's `test_pricing_enrichment_service.py` pattern.
- [x] **II. SOLID**: `ReturnsEnrichmentService` is a new, single-responsibility class (computes
  exactly `position_return`/`weighted_position_return`, nothing else) — added by composition into
  `IngestionService` (a new constructor parameter, one new call in the pipeline), not by modifying
  `PricingEnrichmentService`'s internals. This is Open/Closed: pricing enrichment is extended by
  adding a sibling stage, not edited.
- [x] **III. Type Safety**: New module will carry full type annotations, pass `mypy --strict`, and
  be `ruff check`/`ruff format` clean, consistent with the rest of `app/services/`.
- [x] **IV. Observability**: `ReturnsEnrichmentService.enrich()` will emit a structured
  `structlog` info-level event (row count, sub-account count) on completion, mirroring
  `pricing_enrichment_service.py`'s `enrich_complete` event.
- [x] **V. RESTful/OpenAPI**: No new resources or verbs — extends the existing
  `GET /v1/accounts/{account_name}/position` attribute enum and
  `GET /v1/positions/attributes` metadata response. `contracts/openapi.yaml` for this feature
  documents the extended enum. HATEOAS `_links` and RFC 7807 error shapes are unchanged (no new
  error conditions — zero-denominator cases are handled by the existing fail-soft-to-0 pattern,
  not new exceptions).
- [x] **No principle violations**: Complexity Tracking table left empty — no deviations.

## Project Structure

### Documentation (this feature)

```text
specs/006-ladder-daily-returns/
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
├── services/
│   ├── returns_enrichment_service.py   # NEW — ReturnsEnrichmentService
│   ├── pricing_enrichment_service.py   # unchanged (feature 002)
│   ├── ingestion_service.py            # MODIFIED — chain ReturnsEnrichmentService after
│   │                                    #   PricingEnrichmentService in ingest()
│   └── position_attributes.py          # MODIFIED — add position_return and
│                                        #   weighted_position_return to ATTRIBUTE_DEFINITIONS,
│                                        #   SUPPORTED_ATTRIBUTES, COLUMN_FOR_ATTRIBUTE
├── repositories/
│   └── ladder_repository.py            # unchanged — read_full_df already returns all stored
│                                        #   columns generically; read_ladder_df's explicit
│                                        #   column allowlist already excludes derived columns
├── api/
│   ├── ladder.py                       # MODIFIED — _get_ingestion_service wires
│   │                                    #   ReturnsEnrichmentService into IngestionService
│   │                                    #   (no request/response shape change)
│   └── position_timeseries.py          # unchanged — already generic over
│                                        #   position_attributes.ATTRIBUTE_DEFINITIONS
└── models/
    └── ladder.py                       # unchanged (IngestionSummary shape unaffected)

tests/
├── unit/
│   └── test_returns_enrichment_service.py   # NEW
├── features/
│   └── ladder_returns.feature               # NEW — User Stories 1–3 (compute + persist)
│   └── retrieve_position_timeseries.feature # MODIFIED — add User Story 4 scenarios
│                                              #   (or a new feature file; decided in tasks.md)
└── steps/
    └── ladder_returns_steps.py              # NEW
```

**Structure Decision**: Single existing web-service project (`app/` + `tests/`), no new
top-level directories. This feature follows the same shape as feature 002 (ladder market data
enrichment): one new stateless enrichment service, one new call site in the existing ingestion
pipeline, and additive-only entries in the existing attribute registry consumed by the existing
position time series endpoint. No new API resources, no new persistence mechanism.

## Complexity Tracking

*No Constitution Check violations — table intentionally left empty.*
