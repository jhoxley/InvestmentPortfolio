# Implementation Plan: VaR Contributions (Marginal Risk) Endpoint

**Branch**: `015-var-contributions` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-var-contributions/spec.md`

## Summary

Add `GET /v1/accounts/{account}/risk/var/contributions`, a read-only endpoint that decomposes an
already-computed VaR estimate into per-position or per-theme standalone VaR, incremental VaR,
component Expected Shortfall and marginal VaR. It reuses feature 012's historical-simulation engine
and feature 013's store-reading conventions, but needs one new capability underneath both: the
engine currently only ever returns the *aggregate* scenario PnL vector, never the per-position PnL
matrix that decomposition requires, and the per-instrument aligned returns used to build that matrix
are discarded at the end of every run. This feature (a) extracts the existing scenario-matrix-building
logic in `app/services/var/engine.py` into a reusable function so both the aggregate estimate and the
new decomposition are computed from one matrix, (b) adds a small set of pure decomposition functions
over that matrix, (c) persists an accumulating per-account "scenario returns snapshot" so a
contributions request never needs a market-data call or a new run, and (d) adds the `theme` field the
spec's `group_by=theme` option needs — which, on inspection, does not yet exist anywhere in this
service's data model (see research.md §4).

## Technical Context

**Language/Version**: Python 3.12 (matches the rest of the service; numpy 2.5's stubs require it)
**Primary Dependencies**: FastAPI, Pydantic, pandas, numpy, structlog — all already in use by
features 012/013; no new dependency is introduced.
**Storage**: Filesystem CSV/JSON under `data/{account}/var/`, extending the existing `VarRepository`
layout (feature 012) with one new accumulating store for the scenario returns snapshot.
**Testing**: pytest (unit + BDD/Gherkin via pytest-bdd), matching the rest of the service.
**Target Platform**: Local Windows/Linux server (uvicorn/FastAPI), same as the rest of the service.
**Project Type**: Single existing FastAPI web service (`app/`); no new top-level project.
**Performance Goals**: Sub-second response for an already-computed date (SC-002), matching the
existing VaR series endpoint; no market-data network calls and no new calculation run triggered.
**Constraints**: Must not require a new VaR calculation run or any market-data lookup to serve a
request (FR-007). Must reuse the existing estimates/outcomes store's quality and "not computed"
conventions exactly (FR-009, FR-010).
**Scale/Scope**: One endpoint, one new repository-level store, one new pure decomposition module;
per-request matrix size at most ~1,300 scenario rows x ~60 positions (the largest configured
look-back x the largest account's position count) — comparable to the existing engine's per-date,
per-lookback `estimate()` call, so no new performance regime is introduced.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: BDD Gherkin scenarios already defined in spec.md (3 user stories); test tasks
  (unit tests for the new decomposition functions and repository methods, BDD steps for the endpoint)
  precede implementation tasks in tasks.md (feature 012/013 precedent followed).
- [x] **II. SOLID**: Decomposition math stays in pure functions (engine.py / new `contributions.py`),
  independent of I/O — mirrors the existing `estimate()`/`var_es()` separation. The new persisted-
  snapshot store is a new method set on the existing `VarRepository`, not a new god-object. The new
  `VarContributionsService` follows the single-responsibility pattern of `VarSeriesService`/
  `VarBacktestService` — one orchestrator per endpoint, each depending only on abstractions
  (`AccountsService`, `VarRepository`, `VarSettings`) already used elsewhere.
- [x] **III. Type Safety**: New Pydantic response models in `app/models/var_series.py` (alongside the
  existing read-side models); full type annotations and docstrings on every new function; `ruff` and
  `mypy --strict` must stay clean, matching the existing codebase's zero-error baseline.
- [x] **IV. Observability**: A `var_contributions_request` structured log event (account, date,
  lookback, confidence, group_by, group_count) mirrors `var_series_request`; a
  `var_contributions_snapshot_persisted` event on the write side added to `VarRunService`.
- [x] **V. RESTful/OpenAPI**: New GET resource under the existing `/v1/accounts/{account}/risk/var/`
  namespace; HATEOAS `_links` (self, status, runs) and RFC 7807 errors reuse the existing
  `_var_problem` helper and `InvalidVarQueryError` type (see research.md §3 for why no new problem
  type is introduced, correcting the spec's literal wording). OpenAPI spec (`contracts/openapi.yaml`)
  defines the new path.
- [x] **No principle violations**: None identified; Complexity Tracking left empty below.

## Project Structure

### Documentation (this feature)

```text
specs/015-var-contributions/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── openapi.yaml
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── api/
│   └── risk_var.py                      # EXTEND: new GET .../risk/var/contributions route
├── models/
│   ├── var_series.py                    # EXTEND: ContributionGroupEntry, VarContributionsResponse
│   └── market_data.py                   # EXTEND: IdentifierMappingEntry gains optional `theme`
├── repositories/
│   ├── var_repository.py                # EXTEND: scenario-returns snapshot read/write methods
│   └── identifier_mapping_repository.py # EXTEND: expose theme lookup (no schema change needed)
├── services/
│   └── var/
│       ├── engine.py                    # EXTEND: extract scenario-matrix builder for reuse
│       ├── exposures.py                 # EXTEND: theme lookup helper for grouping
│       ├── contributions.py             # NEW: pure standalone/incremental/component/marginal math
│       ├── var_run_service.py           # EXTEND: persist the scenario-returns snapshot per run
│       └── var_contributions_service.py # NEW: orchestrates the contributions endpoint
└── exceptions.py                        # No new exception type (research.md §3)

tests/
├── features/
│   └── var_contributions.feature        # NEW: Gherkin scenarios from spec.md (no numeric
│                                         #   prefix, matching var_calculation_runs.feature /
│                                         #   var_series_backtest_api.feature convention)
├── steps/
│   └── var_contributions_steps.py       # NEW
└── unit/
    ├── test_var_contributions_engine.py     # NEW: standalone/incremental/component/marginal math
    ├── test_var_contributions_service.py    # NEW: not-computed/insufficient/grouping behaviour
    └── test_var_repository_scenario_returns.py  # NEW: snapshot upsert/read round-trip
```

**Structure Decision**: Single existing FastAPI project (`app/`), consistent with features
012/013/014. This feature adds one new pure-math module (`app/services/var/contributions.py`) and one
new orchestration service (`app/services/var/var_contributions_service.py`), and makes additive
extensions to five existing files. No new top-level project, no new persisted file *format* (CSV/JSON,
same convention as `VarRepository`), and no new third-party dependency.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
