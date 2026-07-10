# Implementation Plan: Capital Ledger Ingestion

**Branch**: `003-capital-ledger-ingestion` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-capital-ledger-ingestion/spec.md`

## Summary

Add a second ingestable resource to `portfolio-analysis-service`, mirroring the existing
`/v1/accounts/{account_name}/ladder` trio but for a capital ledger: `POST`/`GET`/`GET .../download`
at `/v1/accounts/{account_name}/capital`. The input is the XLSX produced by the
`AccountPreparationPipeline`'s `create_capital_ledger` mode (columns: `date`, `capital`, `income`,
`book_value` — all cumulative, no sub-account dimension). The sparse date-level rows are expanded
into a full Monday–Friday business-day series covering the earliest through latest date *recorded
in the file itself* (not extended to "today," unlike the ladder — there is no pricing step
requiring that freshness boundary), forward-filling each column from its most recent observation.
The calendar-reindex/forward-fill mechanic is extracted out of `LadderExpander` into a shared
helper so the new `CapitalLedgerExpander` genuinely reuses the same code, per the spec's explicit
instruction. The capital ledger is stored independently of any position ladder for the same
account (`capital.xlsx` + `capital_meta.json`, siblings of `ladder.xlsx` + `meta.json`), with its
own checksum-based idempotency/conflict handling and no market-data enrichment step.

## Technical Context

**Language/Version**: Python 3.11 (unchanged)
**Primary Dependencies**: FastAPI 0.115, uvicorn, pandas, openpyxl, structlog, pydantic ≥2.0,
pyyaml (all unchanged — no new dependency; this feature has no market-data/httpx involvement)
**Storage**: Local filesystem, unchanged layout convention. New sibling files per account:
`data/{account_name}/capital.xlsx` + `data/{account_name}/capital_meta.json`, fully independent
of the existing `ladder.xlsx` + `meta.json` pair for the same account
**Testing**: pytest 8, pytest-bdd 7 (unchanged). No new fakes/mocks needed — this feature makes no
outbound HTTP calls, so the existing `app_client` fixture (which already stubs the ladder
feature's market-data dependencies) works for capital tests without modification
**Target Platform**: Local development machine / localhost server (unchanged)
**Project Type**: Web service (REST API) — single existing FastAPI application, extended
**Performance Goals**: Matches feature 001's ladder ingestion budget (SC-001: ≤10s for files with
up to 5,000 recorded rows) — if anything, faster in practice since there is no outbound
market-data call to wait on
**Constraints**: No authentication (matches existing trusted-local-service pattern); capital
ledger writes MUST be atomic and MUST leave any existing stored ladder/capital ledger completely
untouched on failure (same pattern as `LadderRepository`)
**Scale/Scope**: Single user / local instance; no concurrent-write safety required (unchanged
from feature 001)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: BDD Gherkin scenarios already defined in spec.md for all four user
  stories; new `.feature` files and step implementations will be written and left failing before
  any production code is added (tasks.md will sequence test tasks first)
- [x] **II. SOLID**: New single-responsibility components — `CapitalLedgerValidator` (schema
  checks only), `CapitalLedgerExpander` (expansion only, delegating the shared reindex/ffill
  mechanic to `expand_business_days()` rather than duplicating `LadderExpander`'s logic —
  Open/Closed via extraction, not modification of ladder behaviour), `CapitalRepository`
  (persistence only), `CapitalIngestionService` (orchestration only, no market-data dependency it
  doesn't need — Interface Segregation). `LadderExpander`'s refactor to delegate to the shared
  helper is behaviour-preserving (existing `test_ladder_expander.py` continues to pass unchanged)
- [x] **III. Type Safety**: `ruff check` / `ruff format` / `mypy --strict` continue to gate all
  new code; Pydantic models used for `CapitalIngestionSummary`, `CapitalSummary`, and `CapitalMeta`
- [x] **IV. Observability**: structlog JSON logging planned for capital ingestion/refresh/conflict
  events, following the existing `logger.bind(...)` pattern in `ingestion_service.py`
- [x] **V. RESTful/OpenAPI**: New resource modelled as a noun (`capital`) under the existing
  `/v1/accounts/{account_name}/` path prefix; `contracts/openapi.yaml` documents the new
  POST/GET/download trio; HATEOAS `_links` (self, download) and RFC 7807 errors used throughout,
  matching the existing ladder endpoints
- [x] **No principle violations**: No deviations to justify

## Project Structure

### Documentation (this feature)

```text
specs/003-capital-ledger-ingestion/
├── plan.md              # This file
├── research.md          # Phase 0 findings
├── data-model.md         # Entity definitions and storage/schema
├── quickstart.md        # Developer getting-started guide
├── contracts/
│   └── openapi.yaml     # New capital POST/GET/download paths (v0.3.0)
└── tasks.md              # Generated by /speckit-tasks
```

### Source Code

```text
portfolio-analysis-service/
├── app/
│   ├── exceptions.py                       # + EmptyCapitalDateRangeError
│   ├── api/
│   │   └── capital.py                       # NEW: POST/GET/download routes, mirrors ladder.py
│   │                                         # but with simpler DI (no market-data client /
│   │                                         # identifier-mapping repo dependencies)
│   ├── models/
│   │   └── capital.py                       # NEW: CapitalIngestionSummary, CapitalSummary
│   │                                         # (reuses Links from app.models.ladder)
│   ├── repositories/
│   │   └── capital_repository.py            # NEW: CapitalMeta + CapitalRepository, mirrors
│   │                                         # LadderRepository (capital.xlsx + capital_meta.json)
│   ├── services/
│   │   ├── business_day_expansion.py        # NEW: shared expand_business_days() helper,
│   │   │                                    # extracted from LadderExpander (research.md §1)
│   │   ├── ladder_expander.py               # MODIFIED: delegates to the shared helper per
│   │   │                                    # sub-account group; behaviour unchanged
│   │   ├── capital_ledger_expander.py       # NEW: CapitalLedgerExpander — no grouping, no
│   │   │                                    # closure rule, range = [min(date), max(date)] of
│   │   │                                    # the file itself (no `today` parameter)
│   │   └── capital_ingestion_service.py     # NEW: CapitalIngestionService — validate → expand
│   │                                        # → persist orchestration; no enrichment step
│   ├── validators/
│   │   └── capital_ledger.py                # NEW: CapitalLedgerValidator — required columns
│   │                                        # date/capital/income/book_value, non-empty,
│   │                                        # parseable date, numeric values, non-empty
│   │                                        # business-day range over [min(date), max(date)]
│   └── main.py                              # + capital router registration, +
│                                             # EmptyCapitalDateRangeError exception handler (422)
├── tests/
│   ├── features/
│   │   ├── ingest_capital.feature            # US1, US3, US4 scenarios
│   │   └── retrieve_capital.feature           # US2 scenarios
│   ├── steps/
│   │   ├── ingest_capital_steps.py
│   │   └── retrieve_capital_steps.py
│   └── unit/
│       ├── test_business_day_expansion.py    # shared helper's reindex/ffill behaviour
│       ├── test_capital_ledger_validator.py
│       └── test_capital_ledger_expander.py   # forward-fill, [min,max] boundary, no closure rule
```

**Structure Decision**: Additive extension of the existing single-project layering (`api/` →
`services/` → `repositories/` → `validators/`), matching feature 001's structure decision. One
small internal refactor (`ladder_expander.py` delegating to a new `business_day_expansion.py`
helper) is required to satisfy the spec's explicit "same code/logic" instruction without
duplicating logic; this is behaviour-preserving and covered by the existing
`test_ladder_expander.py` suite plus a new focused unit test for the extracted helper. No new
top-level project, service, or third-party dependency is introduced.

## Complexity Tracking

> No principle violations — table not required.
