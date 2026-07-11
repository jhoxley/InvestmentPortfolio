# Implementation Plan: Account Time Series API

**Branch**: `004-account-timeseries-api` | **Date**: 2026-07-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-account-timeseries-api/spec.md`

## Summary

Add three read-only endpoints to `portfolio-analysis-service`: a main time series endpoint
(`GET /v1/accounts/{account_name}/timeseries`) that joins an account's already-ingested capital
ledger and position ladder into a single per-business-day series of caller-selected attributes
(`capital`, `income`, `book_cost`, `market_value`, `pnl`), a metadata endpoint
(`GET /v1/timeseries/attributes`) describing those attributes, and an accounts-enumeration
endpoint (`GET /v1/accounts`) listing every ingested account with each resource's date range.
The join reuses the existing `expand_business_days()` helper (built in feature 003) on both the
capital-ledger side and an aggregated (summed-by-date) position-ladder side, so forward-fill
behaviour is identical and already-tested on both halves of the join. Missing-source and
invalid-date-range conditions fail the whole request (RFC 7807, no partial results), matching
the existing ingestion endpoints' all-or-nothing validation pattern. No new dependency, no new
external calls — everything is read from already-stored `ladder.xlsx`/`capital.xlsx` files.

## Technical Context

**Language/Version**: Python 3.11 (unchanged)
**Primary Dependencies**: FastAPI 0.115, uvicorn, pandas, openpyxl, structlog, pydantic ≥2.0,
pyyaml (all unchanged — no new dependency; this feature makes no outbound HTTP calls)
**Storage**: Local filesystem, unchanged. Read-only against the existing
`data/{account_name}/{ladder.xlsx,meta.json,capital.xlsx,capital_meta.json}` layout — this
feature writes nothing new to disk
**Testing**: pytest 8, pytest-bdd 7 (unchanged). No new fakes/mocks needed — purely reads
already-stored files via the existing `app_client` fixture and fixture-seeded ingestion calls
**Target Platform**: Local development machine / localhost server (unchanged)
**Project Type**: Web service (REST API) — single existing FastAPI application, extended
**Performance Goals**: SC-001 — a full multi-year (~2,600 business day) time series returns
within 5 seconds; this is an in-memory pandas join over already-parsed local files, expected to
be well within budget
**Constraints**: No authentication (matches existing trusted-local-service pattern); read-only —
MUST NOT write to or mutate any stored ledger; missing-data failures MUST be whole-request
fail-fast (FR-015), never partial/null results
**Scale/Scope**: Single user / local instance; no concurrent-write safety required (unchanged
from prior features — this feature performs no writes at all)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: BDD Gherkin scenarios already defined in spec.md for all three user
  stories; new `.feature` files and step implementations will be written and left failing
  before any production code is added (tasks.md will sequence test tasks first)
- [x] **II. SOLID**: New single-responsibility components — `TimeseriesDateResolver` (date
  defaulting/adjustment only), `TimeSeriesService` (join/aggregation/computation only,
  depending on `AccountsService` and the two repositories via constructor injection —
  Dependency Inversion), `AccountsService` (account existence + per-resource date-range lookup
  only, shared by both the main endpoint's validation and the enumeration endpoint — avoiding
  duplicated account-listing logic). Extracting `account_name` validation and repository DI
  providers into shared modules (research.md §4) is a behaviour-preserving refactor of
  existing duplicated code, not new duplication
- [x] **III. Type Safety**: `ruff check` / `ruff format` / `mypy --strict` continue to gate all
  new code; Pydantic models used for all five new response/request shapes
- [x] **IV. Observability**: structlog JSON logging planned for each time series request
  (account_name, attributes, resolved date range, row count, outcome) and each validation
  failure, following the existing `logger.bind(...)` pattern
- [x] **V. RESTful/OpenAPI**: Three new noun-resource endpoints (`timeseries`, `accounts`)
  under the existing `/v1/` prefix; `contracts/openapi.yaml` documents all three; HATEOAS
  `_links` and RFC 7807 errors used throughout, matching existing endpoints. `/v1/accounts` is
  the "list" verb the existing `/v1/accounts/{account_name}/...` item-detail family has never
  had — a natural completion of that resource family, not a new one
- [x] **No principle violations**: No deviations to justify

## Project Structure

### Documentation (this feature)

```text
specs/004-account-timeseries-api/
├── plan.md              # This file
├── research.md          # Phase 0 findings
├── data-model.md         # Entity definitions and storage/schema
├── quickstart.md        # Developer getting-started guide
├── contracts/
│   └── openapi.yaml     # New timeseries/attributes/accounts paths (v0.4.0)
└── tasks.md              # Generated by /speckit-tasks
```

### Source Code

```text
portfolio-analysis-service/
├── app/
│   ├── exceptions.py                        # + NoAttributesRequestedError,
│   │                                         # UnsupportedAttributeError, FutureEndDateError,
│   │                                         # InvalidDateRangeError, MissingRequiredSourceError
│   ├── api/
│   │   ├── dependencies.py                  # NEW: shared get_ladder_repository() /
│   │   │                                    # get_capital_repository() providers, extracted
│   │   │                                    # from ladder.py / capital.py (research.md §4)
│   │   ├── ladder.py                        # MODIFIED: uses shared account_name validator +
│   │   │                                    # dependencies.py providers; no behaviour change
│   │   ├── capital.py                       # MODIFIED: same as above
│   │   ├── timeseries.py                    # NEW: GET /accounts/{account_name}/timeseries,
│   │   │                                    # GET /timeseries/attributes
│   │   └── accounts.py                      # NEW: GET /accounts
│   ├── models/
│   │   └── timeseries.py                    # NEW: TimeSeriesEntry, TimeSeriesResponse,
│   │                                        # AttributeDefinition, AttributeMetadataResponse,
│   │                                        # AccountResourceRange, AccountSummary,
│   │                                        # AccountsResponse
│   ├── repositories/
│   │   ├── ladder_repository.py             # + read_full_df(), list_accounts()
│   │   └── capital_repository.py            # + read_df(), list_accounts()
│   ├── services/
│   │   ├── timeseries_attributes.py         # NEW: single-source-of-truth attribute
│   │   │                                    # definitions (name, description, source,
│   │   │                                    # required-source flags) — used by both
│   │   │                                    # validation (FR-004) and metadata (FR-017)
│   │   ├── timeseries_date_resolver.py      # NEW: TimeseriesDateResolver (research.md §3)
│   │   ├── accounts_service.py              # NEW: AccountsService — account existence +
│   │   │                                    # per-resource date-range lookup, shared by the
│   │   │                                    # main endpoint and the enumeration endpoint
│   │   └── timeseries_service.py            # NEW: TimeSeriesService — orchestrates
│   │                                        # validation, date resolution, join, pnl
│   │                                        # computation (data-model.md relationships)
│   ├── validators/
│   │   └── account_name.py                  # NEW: shared ACCOUNT_NAME_PATTERN +
│   │                                        # validate_account_name(), extracted from
│   │                                        # ladder.py/capital.py (research.md §4)
│   └── main.py                              # + timeseries.router, accounts.router
│                                             # registrations, + 5 new exception handlers
├── tests/
│   ├── features/
│   │   ├── retrieve_timeseries.feature       # US1 scenarios
│   │   ├── timeseries_attribute_metadata.feature  # US2 scenarios
│   │   └── list_accounts.feature             # US3 scenarios
│   ├── steps/
│   │   ├── retrieve_timeseries_steps.py
│   │   ├── timeseries_attribute_metadata_steps.py
│   │   └── list_accounts_steps.py
│   └── unit/
│       ├── test_timeseries_date_resolver.py
│       ├── test_timeseries_service.py
│       └── test_accounts_service.py
```

**Structure Decision**: Additive extension of the existing single-project layering (`api/` →
`services/` → `repositories/` → `validators/`), matching features 001–003. Two small refactors
of existing files (`ladder.py`, `capital.py` delegating to newly-shared `dependencies.py` and
`validators/account_name.py`) are required because this feature is the third consumer of logic
those files previously duplicated (research.md §4) — both are behaviour-preserving and covered
by the existing ladder/capital BDD suites, which MUST continue to pass unmodified. No new
top-level project, service, or third-party dependency is introduced.

## Complexity Tracking

> No principle violations — table not required.
