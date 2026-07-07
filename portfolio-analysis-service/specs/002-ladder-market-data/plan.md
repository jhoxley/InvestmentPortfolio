# Implementation Plan: Ladder Market Data Enrichment

**Branch**: `002-ladder-market-data` | **Date**: 2026-07-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-ladder-market-data/spec.md`

## Summary

Extend the existing `portfolio-analysis-service` ingestion pipeline so that, after a sub-account
ledger is expanded into a daily position ladder, each row is enriched with `price`,
`market_value`, and `portfolio_weight`. Prices are sourced from the already-running
`market-data-web-service` via one batched HTTP request per distinct non-Cash sub-account
(spanning that sub-account's full active date range, requested in GBP), resolved through a
configured JSON identifier-mapping file (sub-account name → `ticker`/`isin`). Cash is always
priced synthetically at 1.0 GBP. Any unresolvable identifier or price gap aborts the ingestion
with a descriptive error before anything is persisted. Re-submitting an unchanged-checksum
ledger now re-runs enrichment against the previously stored ladder rows (without re-expanding
them) and reports a `refreshed` status. `run_end_to_end.ps1` is updated to wire the two
services' host/port together instead of leaving the integration commented out.

## Technical Context

**Language/Version**: Python 3.11 (unchanged)
**Primary Dependencies**: FastAPI 0.115, uvicorn, pandas, openpyxl, structlog, pydantic ≥2.0,
pyyaml, **httpx** (promoted from dev-only to a runtime dependency — used as the HTTP client for
calling `market-data-web-service`; already vendored transitively via FastAPI's `TestClient` so no
new third-party dependency is introduced)
**Storage**: Unchanged local filesystem layout (`data/{account}/ladder.xlsx` + `meta.json`).
`ladder.xlsx` gains three trailing columns (`price`, `market_value`, `portfolio_weight`). The
identifier-mapping JSON file is an external, read-only input owned outside this repository
(referenced by configured path — not copied into the service's own data store)
**Testing**: pytest 8, pytest-bdd 7 (unchanged). The `market-data-web-service` HTTP boundary is
faked in tests via `httpx.MockTransport` (built into `httpx`; no new test dependency needed)
rather than live network calls
**Target Platform**: Local development machine / localhost server (unchanged)
**Project Type**: Web service (REST API)
**Performance Goals**: Enrichment adds at most one HTTP round trip per distinct non-Cash
sub-account (per SC-003); for a typical ladder of ≤10 sub-accounts against a local
`market-data-web-service` instance this is expected to add a few seconds to the existing
ingestion budget (feature 001: ≤10s for 5,000 rows). No new hard latency ceiling is introduced
beyond "one request per sub-account, never per date" — this is a deliberate scope choice, not an
oversight. Soft target: if enrichment routinely adds more than ~10s for a ladder of ≤10
sub-accounts against a local market-data-web-service instance, treat that as a signal to revisit
this budget (e.g., investigate the market-data-service's own response time) rather than as an
immediate hard failure
**Constraints**: Base currency fixed at GBP; no authentication between the two services
(matches the existing trusted-local-service pattern); enrichment failures MUST leave the
previously stored ladder (if any) completely untouched (atomic write, unchanged from feature 001)
**Scale/Scope**: Single user / local instance; no concurrent-write safety required (unchanged
from feature 001)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: BDD Gherkin scenarios already defined in spec.md for all four user
  stories (including the identifier-precedence and refreshed-status clarifications); new
  `.feature` files and their step implementations will be written and left failing before any
  production code is added (tasks.md will sequence test tasks first)
- [x] **II. SOLID**: New single-responsibility components — `IdentifierMappingRepository` (loads
  and looks up the mapping file), a `MarketDataClient` protocol + `HttpMarketDataClient`
  implementation (isolates the HTTP boundary behind an abstraction so it can be faked in tests —
  Dependency Inversion), and `PricingEnrichmentService` (orchestrates resolve → fetch → validate
  → compute, independent of `IngestionService`'s existing validate → checksum → expand →
  persist steps, which it extends without modifying their internals — Open/Closed)
- [x] **III. Type Safety**: `ruff check` / `ruff format` / `mypy --strict` continue to gate all
  new code; Pydantic models used for the identifier-mapping entries, the market-data client's
  response shape, and the two new config sections
- [x] **IV. Observability**: structlog JSON logging planned for every market-data-service call
  (sub_account, identifier, date range, duration, outcome), every mapping resolution failure,
  and every price-coverage failure, following the existing `logger.bind(...)` pattern in
  `ingestion_service.py`
- [x] **V. RESTful/OpenAPI**: No new endpoints or resources — the existing `/v1/accounts/
  {account_name}/ladder` POST/GET/download trio is extended, not replaced. `contracts/
  openapi.yaml` is updated for the changed `IngestionSummary.status` enum and the two new RFC
  7807 error responses (422 for mapping/coverage problems, 502 for an unreachable market-data
  service). HATEOAS `_links` and `/v1/` prefix are unchanged
- [x] **No principle violations**: No deviations to justify

## Project Structure

### Documentation (this feature)

```text
specs/002-ladder-market-data/
├── plan.md              # This file
├── research.md          # Phase 0 findings
├── data-model.md         # Entity definitions and storage/schema changes
├── quickstart.md        # Developer getting-started guide (config + mapping file)
├── contracts/
│   └── openapi.yaml     # Updated OpenAPI 3.1 contract (status enum, new error responses)
└── tasks.md              # Generated by /speckit-tasks
```

### Source Code

```text
portfolio-analysis-service/
├── app/
│   ├── config.py                          # + MarketDataServiceSettings, IdentifierMappingSettings
│   ├── exceptions.py                      # + IdentifierMappingError, PriceCoverageError,
│   │                                        MarketDataServiceError
│   ├── api/
│   │   └── ladder.py                       # unchanged routes; DI wiring picks up the new
│   │                                        PricingEnrichmentService
│   ├── clients/
│   │   ├── __init__.py
│   │   └── market_data_client.py           # MarketDataClient protocol + HttpMarketDataClient
│   │                                        (httpx-based; one call per sub-account)
│   ├── models/
│   │   ├── ladder.py                       # IngestionSummary.status: "created" | "refreshed"
│   │   │                                    (renamed from "unchanged" — see research.md)
│   │   └── market_data.py                  # IdentifierMappingEntry, PriceHistoryPoint
│   ├── repositories/
│   │   ├── ladder_repository.py            # + read_ladder_df() to support the refresh path
│   │   └── identifier_mapping_repository.py # loads + looks up the configured mapping JSON
│   └── services/
│       ├── ingestion_service.py            # extended: calls PricingEnrichmentService before
│       │                                    persisting, on both the new-ladder and
│       │                                    checksum-match (refresh) paths
│       └── pricing_enrichment_service.py   # resolves identifiers, batches market-data calls,
│                                            validates coverage, computes market_value + weight
├── tests/
│   ├── conftest.py                         # + fake_market_data_service fixture (httpx.MockTransport)
│   ├── features/
│   │   ├── ladder_pricing.feature          # US1 + US3 scenarios
│   │   ├── batch_pricing.feature           # US2 scenarios
│   │   └── market_data_config.feature      # US4 scenarios
│   ├── steps/
│   │   ├── ladder_pricing_steps.py
│   │   ├── batch_pricing_steps.py
│   │   └── market_data_config_steps.py
│   └── unit/
│       ├── test_pricing_enrichment_service.py
│       ├── test_identifier_mapping_repository.py
│       └── test_market_data_client.py
├── config.yaml                             # + market_data_service + identifier_mapping blocks
└── (pyproject.toml / requirements.txt      # httpx moved from [project.optional-dependencies.dev]
                                              to [project.dependencies])

run_end_to_end.ps1 (repo root)               # Phase 2 config block un-commented and populated
                                              with $MarketDataHost/$MarketDataPort and the
                                              InvestmentDataStatic.json path
```

**Structure Decision**: Additive extension of the existing single-project layering
(`api/` → `services/` → `repositories/`), with one new `clients/` package for the outbound
HTTP boundary to `market-data-web-service`. No new top-level project or service is introduced;
this stays a single FastAPI application, consistent with feature 001's structure decision.

## Complexity Tracking

> No principle violations — table not required.
