# Implementation Plan: Historical-Simulation VaR Calculation Runs

**Branch**: `012-var-calculation-runs` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-var-calculation-runs/spec.md`
**Methodology**: [`docs/proposals/value-at-risk.md`](../../docs/proposals/value-at-risk.md) §3, §5

## Summary

Add asynchronous VaR calculation **runs** to the risk endpoint group:
- `POST /v1/accounts/{a}/risk/var/runs` (202 + run resource; 409 when one is active)
- `GET …/runs`, `GET …/runs/{run_id}`
- `GET …/risk/var/status`

A process-wide single-worker scheduler executes runs one at a time. Each run:
1. reads the ladder once;
2. selects missing, stale or pending dates (`missing`) or every date (`full`) using per-date
   fingerprints;
3. fetches **observed-only** GBP prices from market-data (`fill=none`) for held instruments and
   their configured proxies;
4. builds a business-day return panel;
5. computes, in vectorised pure functions, the scenario PnL per as-of date, then VaR (k-th largest
   loss, integer rank) and ES (Acerbi–Tasche) at 95/97.5/99% for 260/520/1300-day look-backs, with
   proxy / rescale treatment, coverage and quality;
6. computes hypothetical and ladder PnL outcomes;
7. upserts CSV files under `data/{account}/var/` all-or-none.

Runs left active at start-up are marked failed (`interrupted`). Two PowerShell entry points trigger
and poll runs. No new dependencies.

## Technical Context

**Language/Version**: Python 3.11+ (as for all previous features)
**Primary Dependencies**: FastAPI 0.139, pandas 3.0, numpy 2.5, Pydantic 2.13, httpx 0.28,
structlog 26.1, PyYAML. All already pinned. Stdlib: `concurrent.futures`, `threading`, `hashlib`,
`fractions`, `uuid`, `csv`/pandas CSV.
**Storage**: Filesystem. New per-account `data/{account}/var/` (CSV + JSON) beside the existing
ladder files; atomic temp-file + `os.replace`.
**Testing**: pytest unit tests (`tests/unit/`), pytest-bdd Gherkin (`tests/features/` +
`tests/steps/`), with the existing `FakeMarketDataService` extended for `fill=none` and an inline run
scheduler. The PowerShell scripts are validated through quickstart steps.
**Target Platform**: Locally hosted uvicorn service on Windows (also runs on Linux)
**Project Type**: Single web-service project (existing `app/` layout)
**Performance Goals**: POST acknowledged in < 1 s (SC-002). Full run for about 10 years × 50
positions in < 60 s once prices are cached (SC-003); the budget is about 7 s ladder read, plus
≤ 70 market-data calls, plus < 2 s maths. No-op `missing` run < 15 s (SC-004). Status < 2 s without
reading the ladder (SC-007).
**Constraints**: Never use gap-filled prices; fail closed (FR-026). Store writes are all-or-none
(FR-022). Runs are serialised (FR-018). Existing endpoints' behaviour and error format are
unchanged. RFC 7807 for every new error.
**Scale/Scope**: 2 real accounts; ≤ 2,700 dates × 3 look-backs per account; ≤ about 70 identifiers
(held plus proxies); 4 endpoints, 1 router, 1 service package, 1 repository, 2 scripts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Test-First**: The spec has Gherkin scenarios for User Stories 1–7. Tasks will place the
  engine unit tests (rank/ES/rescale/proxy/coverage/quality using the spec's hand-computed values),
  repository and scheduler unit tests, and the BDD steps for stories 1–6 before implementation.
  Story 7 (PowerShell) has no Python test harness; see Complexity Tracking.
- [x] **II. SOLID**:
  - Single-responsibility modules: exposures, return panel, engine, fingerprint, run service,
    status service, repository, scheduler, router.
  - New protocols `ObservedPriceClient` and `RunScheduler` invert dependencies; the existing
    `MarketDataClient` protocol and `PricingEnrichmentService` are unchanged (ISP).
  - `IdentifierMappingEntry` is extended with optional fields only.
  - `compute_daily_portfolio_return` is reused unchanged for ladder PnL.
- [x] **III. Type Safety**: Full annotations and docstrings; `mypy --strict`; `ruff check` and
  `ruff format`. Pydantic at every boundary: request/response models, `VarSettings`, the run record
  JSON, and the market-data response.
- [x] **IV. Observability**:
  - Structured events for run lifecycle and stage durations, instrument treatments, outliers,
    unresolved proxies and interruptions (research §14). The existing request middleware covers HTTP.
    `/health` and `/ready` are unchanged.
  - **Error payloads carry a correlation ID** (FR-033, research §14a): the new problem types add
    `correlation_id`; runs record the creating request's correlation ID; run failures include
    `run_id` and `correlation_id`; background log lines are bound to both. Stack traces are logged,
    not returned (permitted by IV).
  - The *existing* handlers' lack of a correlation ID is an inherited gap, recorded in Complexity
    Tracking.
- [x] **V. RESTful/OpenAPI**:
  - Runs are modelled as a resource collection (POST creates and returns 202 + `Location`; GET
    reads); status is a GET resource.
  - `contracts/openapi.yaml` is updated, with `_links` on every response.
  - New RFC 7807 types: `var-run-in-progress` (409), `var-run-not-found` (404) and
    `invalid-var-run-request` (422). Existing types are reused for account and source errors.
- [x] **No unjustified violations**: The single deviation is recorded below.

**Post-design re-check (after Phase 1)**: data-model, contracts and quickstart introduce no further
deviations. The body is validated in-handler to keep RFC 7807 (research §10), which strengthens
principle V. All gates still pass.

## Project Structure

### Documentation (this feature)

```text
specs/012-var-calculation-runs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml                      # runs + status endpoints
│   ├── market-data-observed-history.md   # consumed contract (market-data feature 009)
│   └── scripts.md                        # refresh-var.ps1 + run_end_to_end.ps1 Phase 7
├── checklists/
│   └── requirements.md
└── tasks.md                              # /speckit-tasks (not created here)
```

### Source Code

```text
app/
├── api/
│   ├── risk_var.py                       # NEW — POST/GET runs, GET run, GET status
│   └── dependencies.py                   # MODIFIED — get_var_repository, get_run_scheduler
├── clients/
│   └── market_data_client.py             # MODIFIED — ObservedPriceClient protocol;
│                                         #   HttpMarketDataClient.get_observed_price_history()
├── models/
│   ├── var.py                            # NEW — VarRunRequest, VarRun, RunWarning, RunFailure,
│   │                                     #   VarRunList, VarStatus, InstrumentTreatment
│   └── market_data.py                    # MODIFIED — IdentifierMappingEntry + var_proxy fields;
│                                         #   ObservedPriceHistory
├── repositories/
│   ├── var_repository.py                 # NEW — estimates/outcomes/instruments CSV, meta, runs;
│   │                                     #   staged all-or-none commit
│   └── identifier_mapping_repository.py  # MODIFIED — entries() for proxy configuration
├── services/
│   └── var/                              # NEW package
│       ├── __init__.py
│       ├── exposures.py                  # ladder → Exposure per date (+ fingerprint input)
│       ├── fingerprint.py                # canonical JSON → sha256
│       ├── return_panel.py               # observed prices → grid returns/observed masks; exclusions
│       ├── engine.py                     # pure: treatments, scenario PnL, rank_k, VaR, ES,
│       │                                 #   coverage, quality, hypothetical PnL
│       ├── run_scheduler.py              # RunScheduler protocol, ThreadRunScheduler, InlineRunScheduler
│       ├── var_run_service.py            # create_run (409 lock), execute (stages), recover_interrupted
│       └── var_status_service.py         # status from meta/CSVs/run records
├── config.py                             # MODIFIED — VarSettings under Settings.var
├── exceptions.py                         # MODIFIED — VarRunInProgressError, VarRunNotFoundError,
│                                         #   InvalidVarRunRequestError, ObservedHistoryUnsupportedError,
│                                         #   InstrumentNotFoundError
└── main.py                               # MODIFIED — include router, 3 handlers, lifespan:
                                          #   recover_interrupted() + scheduler shutdown

tests/
├── conftest.py                           # MODIFIED — FakeMarketDataService supports fill=none,
│                                         #   first/last_observed_date, 404s; inline scheduler override
├── unit/
│   ├── test_var_settings.py              # NEW — VarSettings defaults/overrides, mapping-entry proxy fields
│   ├── test_var_run_scheduler.py         # NEW — inline + single-worker serial execution
│   ├── test_var_engine.py                # NEW — rank_k, VaR/ES (1..520 losses), mini example,
│   │                                     #   exclusion, proxy fill/always/scale, sparse, rescale,
│   │                                     #   coverage precedence, quality, zero-risky edge case
│   ├── test_var_return_panel.py          # NEW — first-return NaN, holiday zeros, exclusions, outliers
│   ├── test_var_exposures.py             # NEW — zero-value exclusion, shared identifiers, Cash
│   ├── test_var_fingerprint.py           # NEW
│   ├── test_var_repository.py            # NEW — upsert, all-or-none on failure, run records
│   ├── test_var_run_service.py           # NEW — date selection (missing/stale/pending/range),
│   │                                     #   409 race lock, failure paths, recovery
│   ├── test_var_status_service.py        # NEW
│   ├── test_market_data_client_observed.py # NEW — fill=none, unsupported detection, 404
│   └── test_risk_var_openapi.py          # NEW — schema presence and links
├── features/
│   └── var_calculation_runs.feature      # NEW — User Stories 1–6
└── steps/
    └── var_calculation_runs_steps.py     # NEW

(repository root)
├── refresh-var.ps1                       # NEW
├── scripts/
│   └── VarRefresh.psm1                   # NEW — shared queue-and-poll helper (Invoke-VarRefresh)
└── run_end_to_end.ps1                    # MODIFIED — Phase 7 VaR, browser → Phase 8
```

**Structure Decision**: Existing single web-service project. VaR gets its own `app/services/var/`
package because it has seven cooperating modules, and its own router file (`risk_var.py`) so the
existing `risk.py` stays closed to modification. Edits to existing files are additive: new optional
model fields, a new protocol and method, new settings, exception types and handlers, router
registration and lifespan hooks.

## Implementation Notes (for /speckit-tasks)

1. **Order**: config, models and exceptions → engine (pure, test-first against spec values) →
   return panel → exposures/fingerprint → repository → client extension → run service + scheduler →
   router and handlers → status → lifespan recovery → BDD → scripts → README update.
2. **Engine numerics**:
   - `rank_k` and ES use integer and `Fraction` arithmetic (research §6).
   - Sort losses once per (date, look-back) with `np.sort`, or `np.partition` on the top m+1.
3. **Weekend and next-day logic** use `pd.offsets.BDay` (Mon–Fri), consistent with the ladder.
4. **Do not** change `PricingEnrichmentService`, `ReturnsEnrichmentService`, the `risk.py` histogram
   or the existing fakes' default behaviour (`fill` absent → today's behaviour).
5. **README**: add the VaR endpoints to the capability table and describe the `var:` config and the
   proxy fields.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Existing endpoints' problem responses (shared `ProblemDetail` / `_problem`) still lack a correlation ID (inherited Principle IV gap) | This feature's new errors and run failures comply (FR-033); changing the shared helper would alter every existing endpoint's error body and tests | Fixing it here widens scope beyond VaR; raise a separate small feature ("add correlation_id to all problem responses"), which the reviewer should log at PR review |
| User Story 7 (PowerShell scripts) has no automated BDD test | The scripts orchestrate already-tested HTTP endpoints from the existing PowerShell pipeline, and the repo has no PowerShell test harness | Adding Pester solely for two thin wrappers adds a new toolchain; the scripts' contract (`contracts/scripts.md`) is verified via quickstart steps 5 and 7, and all the logic they call is covered by Python BDD |
