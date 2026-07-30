# Implementation Plan: Position Time Series API

**Branch**: `005-position-timeseries-api` | **Date**: 2026-07-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-position-timeseries-api/spec.md`

## Summary

Add three read-only endpoints to `portfolio-analysis-service`, grouped under a new
`Position Timeseries` OpenAPI tag: a main endpoint
(`GET /v1/accounts/{account_name}/position`) that returns a per-business-day,
per-position time series of caller-selected attributes (`market_value`, `income`,
`book_cost`, `pnl`, `close_price`, `quantity` — `capital` is not valid here) for one or
more named positions (sub-accounts) within an account, defaulting to every position if
none are named; an enumeration helper (`GET /v1/accounts/{account_name}/positions`)
listing every position ever recorded for an account with its own first/last date; and a
metadata endpoint (`GET /v1/positions/attributes`) describing this endpoint's attribute
set. Unlike the account-level time series endpoint, every attribute here is derivable
from the position ladder alone (no capital ledger join), but the response must track each
position's own active lifecycle independently — still-held positions are forward-filled
to the resolved end date when the ladder is stale, while genuinely divested positions stop
at their real last active date, distinguished by comparing each position's last recorded
row against the ladder's own `to_date`. The response is a flat, tidy list of
`{date, position, ...attributes}` entries, chosen so a Dash/Plotly client can plot
directly from it with no reshaping. No new dependency, no new external calls, and no
repository changes — everything is read via the already-existing
`LadderRepository.read_full_df()`.

## Technical Context

**Language/Version**: Python 3.11 (unchanged)
**Primary Dependencies**: FastAPI 0.115, uvicorn, pandas, openpyxl, structlog, pydantic ≥2.0,
pyyaml (all unchanged — no new dependency; this feature makes no outbound HTTP calls)
**Storage**: Local filesystem, unchanged. Read-only against the existing
`data/{account_name}/{ladder.xlsx,meta.json}` layout — this feature writes nothing new to
disk and does not touch `capital.xlsx`/`capital_meta.json` at all
**Testing**: pytest 8, pytest-bdd 7 (unchanged). No new fakes/mocks needed — purely reads
already-stored files via the existing `app_client` fixture and fixture-seeded ladder
ingestion calls
**Target Platform**: Local development machine / localhost server (unchanged)
**Project Type**: Web service (REST API) — single existing FastAPI application, extended
**Performance Goals**: SC-001 — a 5-year (~1,300 business day) range across all 50 positions
in a typical large account returns within 10 seconds; this is an in-memory pandas groupby
plus per-position reindex/ffill over an already-parsed local file, expected to be well
within budget at this service's single-user scale
**Constraints**: No authentication (matches existing trusted-local-service pattern);
read-only — MUST NOT write to or mutate the stored ladder; no pagination/response-size cap
(FR-020); unrecognised `position` values MUST NOT fail the request (FR-005); missing
position-ladder-at-all MUST fail the whole request (FR-002), but a per-position lack of
data within the resolved range is a normal empty-entries outcome, not a failure
**Scale/Scope**: Single user / local instance; no concurrent-write safety required
(unchanged — this feature performs no writes at all)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: BDD Gherkin scenarios already defined in spec.md for all three user
  stories (including the forward-fill-vs-divested scenarios added during clarification); new
  `.feature` files and step implementations will be written and left failing before any
  production code is added (tasks.md will sequence test tasks first)
- [x] **II. SOLID**: New single-responsibility components — `PositionsService` (position
  enumeration + effective-set intersection only, no date/attribute logic), `PositionTimeSeriesService`
  (orchestrates validation, date resolution, per-position expansion, and pnl computation only,
  depending on `AccountsService`, `PositionsService`, `LadderRepository`, and
  `TimeseriesDateResolver` via constructor injection — Dependency Inversion). Zero changes to
  existing feature 004 components (`AccountsService`, `TimeseriesDateResolver`,
  `expand_business_days`, `LadderRepository.read_full_df`) — all reused unmodified, per the
  Open/Closed principle
- [x] **III. Type Safety**: `ruff check` / `ruff format` / `mypy --strict` continue to gate all
  new code; Pydantic models used for all four new response shapes (reusing
  `AttributeDefinition`/`AttributeMetadataResponse` as-is for the metadata endpoint)
- [x] **IV. Observability**: structlog JSON logging planned for each position time series
  request (account_name, requested positions, effective positions, attributes, resolved date
  range, row count, outcome) and each validation failure, following the existing
  `logger.bind(...)` pattern from `TimeSeriesService`
- [x] **V. RESTful/OpenAPI**: Three new noun-resource endpoints (`position`, `positions`,
  `positions/attributes`) under the existing `/v1/` prefix, grouped under a new
  `Position Timeseries` tag; `contracts/openapi.yaml` documents all three; HATEOAS `_links`
  and RFC 7807 errors used throughout, matching existing endpoints
- [x] **No principle violations**: No deviations to justify

## Project Structure

### Documentation (this feature)

```text
specs/005-position-timeseries-api/
├── plan.md              # This file
├── research.md          # Phase 0 findings
├── data-model.md         # Entity definitions and storage/schema
├── quickstart.md        # Developer getting-started guide
├── contracts/
│   └── openapi.yaml     # New position/positions/positions-attributes paths (v0.5.0)
└── tasks.md              # Generated by /speckit-tasks
```

### Source Code

```text
portfolio-analysis-service/
├── app/
│   ├── exceptions.py                        # + PositionLadderNotIngestedError
│   ├── api/
│   │   ├── position_timeseries.py           # NEW: GET /accounts/{account_name}/position,
│   │   │                                     # GET /accounts/{account_name}/positions,
│   │   │                                     # GET /positions/attributes
│   │   └── (dependencies.py, ladder.py, capital.py, timeseries.py, accounts.py: unchanged)
│   ├── models/
│   │   └── position_timeseries.py           # NEW: PositionSummary, PositionsResponse,
│   │                                         # PositionTimeSeriesEntry,
│   │                                         # PositionTimeSeriesResponse
│   │                                         # (reuses AttributeDefinition /
│   │                                         # AttributeMetadataResponse from
│   │                                         # app/models/timeseries.py as-is)
│   ├── repositories/
│   │   └── ladder_repository.py             # unchanged — read_full_df() already sufficient
│   ├── services/
│   │   ├── position_attributes.py           # NEW: single-source-of-truth attribute
│   │   │                                    # definitions for this endpoint's six-name set
│   │   │                                    # (research.md §5)
│   │   ├── positions_service.py             # NEW: PositionsService — position enumeration
│   │   │                                    # + effective-set intersection (research.md §4)
│   │   └── position_timeseries_service.py   # NEW: PositionTimeSeriesService — orchestrates
│   │                                        # validation, date resolution, per-position
│   │                                        # expansion, pnl computation (data-model.md)
│   │   # (accounts_service.py, timeseries_date_resolver.py, business_day_expansion.py: unchanged)
│   └── main.py                              # + position_timeseries.router registration,
│                                             # + 1 new exception handler
├── tests/
│   ├── features/
│   │   ├── retrieve_position_timeseries.feature   # US1 scenarios
│   │   ├── list_account_positions.feature         # US2 scenarios
│   │   └── position_attribute_metadata.feature     # US3 scenarios
│   ├── steps/
│   │   ├── retrieve_position_timeseries_steps.py
│   │   ├── list_account_positions_steps.py
│   │   └── position_attribute_metadata_steps.py
│   └── unit/
│       ├── test_positions_service.py
│       └── test_position_timeseries_service.py
```

**Structure Decision**: Additive extension of the existing single-project layering (`api/` →
`services/` → `repositories/`), matching features 001–004. No refactor of any existing file is
required this time — feature 004 already extracted the shared `dependencies.py` providers,
`validators/account_name.py`, `AccountsService`, and `TimeseriesDateResolver` that this
feature reuses unmodified. No new top-level project, service, or third-party dependency is
introduced; no repository method changes (`read_full_df()` already returns everything needed,
per research.md §1).

## Complexity Tracking

> No principle violations — table not required.
