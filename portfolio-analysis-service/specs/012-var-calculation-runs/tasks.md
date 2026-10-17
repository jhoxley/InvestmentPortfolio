---

description: "Task list for 012 — Historical-Simulation VaR Calculation Runs"
---

# Tasks: Historical-Simulation VaR Calculation Runs

**Input**: Design documents from `/specs/012-var-calculation-runs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (openapi.yaml,
market-data-observed-history.md, scripts.md), quickstart.md
**Methodology**: `docs/proposals/value-at-risk.md` §3, §5

**Tests**: REQUIRED. The constitution's Principle I makes TDD non-negotiable. Every test task must
be written and **seen to fail** before its implementation task starts. BDD scenarios come from
spec.md's Gherkin blocks and go in `tests/features/var_calculation_runs.feature` with steps in
`tests/steps/var_calculation_runs_steps.py`; each story adds its own scenarios to these two files.

**Organization**: Tasks are grouped by user story. Paths are relative to
`portfolio-analysis-service/` unless prefixed with `(repo root)`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story from spec.md (US1–US7)

## Conventions every task must follow

- Full type annotations; Google-style docstrings on every public symbol; `mypy --strict app/` and
  `ruff check app/ tests/` clean; `ruff format`.
- structlog events use the names in research.md §14 and always bind `account_name` and `run_id`.
- Confidence levels are integer basis points internally (9500/9750/9900); look-backs are
  `{"1y": 260, "2y": 520, "5y": 1300}` from `VarSettings`.
- Business-day arithmetic uses Mon–Fri only (`pd.bdate_range`, `pd.offsets.BDay`), as the ladder does.
- Never modify `app/api/risk.py`, `PricingEnrichmentService`, `ReturnsEnrichmentService`, or the
  default behaviour of the existing `FakeMarketDataService` (requests without `fill` behave as today).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration, models, exceptions and package skeletons that everything else imports.

- [X] T001 Create the package skeleton `app/services/var/__init__.py` (module docstring only) and empty test modules `tests/unit/test_var_engine.py`, `tests/unit/test_var_return_panel.py`, `tests/unit/test_var_exposures.py`, `tests/unit/test_var_fingerprint.py`, `tests/unit/test_var_repository.py`, `tests/unit/test_var_run_service.py`, `tests/unit/test_var_status_service.py`, `tests/unit/test_market_data_client_observed.py`, `tests/unit/test_risk_var_openapi.py`, `tests/features/var_calculation_runs.feature` (Feature header only) and `tests/steps/var_calculation_runs_steps.py` (binds the feature file via `scenarios(...)`, as the other step modules do).
- [X] T002 [P] Write unit tests in `tests/unit/test_var_settings.py`: `Settings()` yields `var.methodology_version == "1.0.0"`, `var.lookbacks == {"1y": 260, "2y": 520, "5y": 1300}`, `var.confidence_levels_bp == [9500, 9750, 9900]`, `min_observed_share_per_scenario == 0.5`, `sparse_density_threshold == 0.8`, `outlier_abs_return == 0.25`, quality defaults (5, 25, 0.8, 20), `excluded_returns == []`; `load_settings()` on a YAML with a `var:` section overrides values; an excluded entry parses `{identifier, date}`.
- [X] T003 Add `VarQualitySettings`, `ExcludedReturn` and `VarSettings` Pydantic models and the `Settings.var: VarSettings = VarSettings()` field in `app/config.py` (research.md §12), making T002 pass.
- [X] T004 [P] Add exception classes to `app/exceptions.py` following the existing style (message attribute, docstrings): `VarRunInProgressError(account_name, active_run_id)`, `VarRunNotFoundError(account_name, run_id)`, `InvalidVarRunRequestError(message, fields)`, `ObservedHistoryUnsupportedError(identifier)`, `InstrumentNotFoundError(identifier)`.
- [X] T005 [P] Create the Pydantic models in `app/models/var.py` per data-model.md and contracts/openapi.yaml: `VarRunMode` (Literal missing|full), `VarRunStatus` (Literal queued|running|succeeded|failed), `VarRunRequest` (`extra="forbid"`; mode default `missing`; optional `start`/`end` dates), `RunWarning`, `RunFailure` (incl. `run_id` and `correlation_id`), `VarRun` (all fields incl. `correlation_id`, counts including `dates_skipped`, warnings, failure, `links` aliased to `_links`, using the `ConfigDict(populate_by_name=True)` pattern from `app/models/risk.py`), `VarRunList`, `DateRange`, `InstrumentTreatment`, `VarStatus`.
- [X] T006 [P] Extend `app/models/market_data.py`: add optional `var_proxy: str | None = None`, `var_proxy_mode: Literal["fill_gaps", "always"] = "fill_gaps"` and `var_proxy_scale: float = Field(default=1.0, gt=0)` to `IdentifierMappingEntry`, and a new `ObservedPriceHistory` model (`points: list[PriceHistoryPoint]`, `first_observed_date: date | None`, `last_observed_date: date | None`). Add a unit test in `tests/unit/test_var_settings.py` (or a new `tests/unit/test_identifier_mapping_entry.py`) proving old entries still validate with defaults, and that `var_proxy_scale=0` and `var_proxy_mode="sometimes"` are rejected.

**Checkpoint**: `mypy --strict app/` and `pytest tests/unit/test_var_settings.py` pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Observed-price client, test fakes, run scheduler, repository and router wiring that
every story uses.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write first, must fail)

- [X] T007 [P] Write `tests/unit/test_market_data_client_observed.py` using `httpx.MockTransport`. Cover:
  - `get_observed_price_history()` sends `fill=none` and `currency=GBP` and parses `prices`, `first_observed_date` and `last_observed_date`;
  - a 200 body **without** `first_observed_date` raises `ObservedHistoryUnsupportedError`;
  - a 404 raises `InstrumentNotFoundError`;
  - a 500, a timeout and a connection error raise `MarketDataServiceError`.
- [X] T008 [P] Write `tests/unit/test_var_repository.py` against a `tmp_path`. Cover:
  - (a) `write_run`/`read_run`/`list_runs` (newest first by `requested_at`) round-trip `VarRun` JSON under `data/{a}/var/runs/{run_id}.json`;
  - (b) `read_estimates`/`read_outcomes`/`read_instruments` return empty DataFrames with the data-model.md columns when no files exist;
  - (c) `commit(account, estimates_upsert, outcomes_upsert, instruments, meta)` replaces all rows for dates present in the upsert and keeps the others, sorted by (date, lookback_days) and by date;
  - (d) if writing any temp file raises (monkeypatch `DataFrame.to_csv` to fail on the third file), **no** existing file changes and no `*.tmp` files remain;
  - (e) `read_meta` returns None before the first commit;
  - (f) `list_accounts_with_runs()` enumerates `data/*/var/runs`.
- [X] T009 [P] Write `tests/unit/test_var_run_scheduler.py`:
  - `InlineRunScheduler.submit` runs the job synchronously;
  - `ThreadRunScheduler` runs two submitted jobs strictly one after the other (record start/end times; the intervals don't overlap) and in submission order;
  - `shutdown()` waits for in-flight work.

### Implementation

- [X] T010 Add the `ObservedPriceClient` Protocol and `HttpMarketDataClient.get_observed_price_history()` in `app/clients/market_data_client.py`, per contracts/market-data-observed-history.md (same logging and timing style as `get_price_history`), making T007 pass. Leave the existing `MarketDataClient` protocol and `get_price_history` unchanged.
- [X] T011 Extend `FakeMarketDataService` in `tests/conftest.py`. When a request carries `fill=none`, return only the configured *observed* points within the range plus `first_observed_date`/`last_observed_date` computed from **all** configured points for the identifier. Add `configure_observed_prices(identifier, points)`, `configure_unsupported_observed_history()` (omits the observed-date fields), and `configure_not_found(identifier)` (404). Requests without `fill` must keep today's behaviour exactly; run the full existing suite to confirm.
- [X] T012 Implement `app/services/var/run_scheduler.py`:
  - `RunScheduler` Protocol (`submit(job: Callable[[], None]) -> None`, `shutdown() -> None`);
  - `ThreadRunScheduler`, wrapping a lazily created `ThreadPoolExecutor(max_workers=1, thread_name_prefix="var-run")`, which logs and swallows exceptions escaping a job (jobs record their own failure);
  - `InlineRunScheduler`;
  - module-level `get_default_scheduler()` returning a process singleton.
  Makes T009 pass.
- [X] T013 Implement `VarRepository` in `app/repositories/var_repository.py` with the CSV columns from data-model.md. The staged all-or-none commit (research.md §5) writes every new file to `tempfile.mkstemp(dir=var_dir, suffix=".tmp")` first, then `os.replace`s them in turn with `meta.json` last, deleting temps on any failure. Run JSON writes are also temp-file + replace. Makes T008 pass.
- [X] T014 Add an `entries() -> list[IdentifierMappingEntry]` method to `IdentifierMappingRepository` in `app/repositories/identifier_mapping_repository.py` (loads lazily as `lookup` does), plus a unit test in `tests/unit/test_var_settings.py` or a new `tests/unit/test_identifier_mapping_repository_entries.py`. Add the same method to `FakeIdentifierMappingRepository` in `tests/conftest.py`, and let `set_entry(...)` accept the optional `var_proxy`, `var_proxy_mode` and `var_proxy_scale` keyword arguments.
- [X] T015 Add three dependency providers to `app/api/dependencies.py`: `get_var_repository`, `get_run_scheduler` (returns `get_default_scheduler()`), and `get_observed_price_client(settings) -> ObservedPriceClient` (returns an `HttpMarketDataClient` built from `settings.market_data_service`, mirroring `_get_market_data_client` in `app/api/ladder.py`). In `tests/conftest.py` `app_client`, override `get_run_scheduler` with an `InlineRunScheduler` and `get_observed_price_client` with `fake_market_data_service.client()`.
- [X] T016 Create `app/api/risk_var.py` with `router = APIRouter(prefix="/v1", tags=["Risk"])` and no routes yet. Register it in `app/main.py` after `risk.router`. Add RFC 7807 handlers in `app/main.py`:
  - `VarRunInProgressError` → 409 `var-run-in-progress`, with `_links.active_run` added to the problem body;
  - `VarRunNotFoundError` → 404 `var-run-not-found`;
  - `InvalidVarRunRequestError` → 422 `invalid-var-run-request`.
  Each handler logs a warning like the existing ones. The three handlers build their body with a new `_var_problem(...)` helper that adds `correlation_id` (from `structlog.contextvars.get_contextvars()`) to the standard fields (FR-033, research.md §14a). The existing `_problem` helper and handlers stay unchanged. Add a unit test, `tests/unit/test_var_problem_details.py`, asserting each of the three problem types carries `correlation_id`, matching the request's logged correlation ID.

**Checkpoint**: The whole existing test suite still passes; new foundational unit tests pass.

---

## Phase 3: User Story 1 - Compute VaR and Expected Shortfall for Every Ladder Date (Priority: P1) 🎯 MVP

**Goal**: A `full` run computes VaR and ES at 95/97.5/99% for 1Y/2Y/5Y on every ladder date from
observed prices (actual returns only; positions with no return are rescaled; proxies come in US3)
and stores them.

**Independent Test**: Seed a ladder and observed prices with hand-chosen values, `POST` a full run
(executed inline in tests), and compare `data/{a}/var/estimates.csv` for a chosen date against the
spec's values.

### Tests for User Story 1 (write first, must fail) ⚠️

- [X] T017 [P] [US1] Write engine unit tests in `tests/unit/test_var_engine.py`:
  - `rank_k(n, p_bp)` for n = 1, 5, 20, 260, 520, 1300 at 9500/9750/9900, including k = 14/7/3, 27/14/6 and 66/33/14, and 1 ≤ k ≤ n for every n in 1..2000;
  - `var_es(losses, p_bp)` on losses 1..520 → VaR 494/507/515 and ES 507.5/514/(2590 + 0.2·515)/5.2 exactly (`pytest.approx` with rel = 1e-12);
  - `scenario_pnl` on the mini example (A 60000, B 30000, Cash 10000; five return pairs) → [-600, -300, -2610, 810, -30], with Cash contributing nothing;
  - the observed-share exclusion drops a row where only 40% of risky value was observed (n = 4);
  - rescale: A 60000 −1%, C 20000 +2%, B 20000 missing → −250;
  - zero risky value → VaR/ES 0, coverage 100/0/0, quality ok.
- [X] T018 [P] [US1] Write return-panel unit tests in `tests/unit/test_var_return_panel.py`:
  - grid returns use the previous **observed** price;
  - the first observed day's return is NaN and earlier days are NaN;
  - unobserved days inside the history are 0.0 with `observed = False`;
  - a return spanning a holiday equals the two-day price ratio;
  - the grid covers exactly the requested Mon–Fri range.
- [X] T019 [P] [US1] Write exposure unit tests in `tests/unit/test_var_exposures.py`. From a ladder DataFrame (columns as stored), `build_exposures(ladder_df, mapping)`:
  - excludes Cash from positions but records `cash_value`;
  - excludes positions with market value 0 or quantity 0;
  - maps sub-account → identifier using `ticker or isin` (same rule as `PricingEnrichmentService`);
  - keeps two sub-accounts sharing one identifier as separate positions;
  - computes risky and total values.
- [X] T020 [P] [US1] Add US1 scenarios to `tests/features/var_calculation_runs.feature`: "Scenario PnL applies historical returns…", "VaR is the k-th largest loss…", "Expected Shortfall is the empirical tail mean", "All three look-backs come from the same scenario history" and "Low-information scenario days are excluded". Implement their steps in `tests/steps/var_calculation_runs_steps.py`:
  - seed the ladder by ingesting a ledger through the existing `app_client` fixtures, or by writing `ladder.xlsx` + `meta.json` with `LadderRepository.write`;
  - seed observed prices via `fake_market_data_service.configure_observed_prices`;
  - shrink look-backs where a scenario says so by overriding `Settings.var.lookbacks` in the test settings;
  - trigger with `POST /v1/accounts/{a}/risk/var/runs {"mode": "full"}`;
  - assert on `VarRepository` reads.
  For the "losses 1..520" scenarios, go through the API: one position worth 100000 GBP, with observed prices built so that scenario day s (s = 1..520) has return −s/100000, giving loss s. Assert VaR and ES within 1e-9 relative tolerance (SC-001).

### Implementation for User Story 1

- [X] T021 [P] [US1] Implement `app/services/var/return_panel.py`:
  - `ReturnPanel` dataclass (grid, identifiers, `returns` T×m float with NaN, `observed` T×m bool, `first_observed`);
  - `build_return_panel(histories: Mapping[str, ObservedPriceHistory], grid_start, grid_end) -> ReturnPanel`, per research.md §6.
  Makes T018 pass.
- [X] T022 [P] [US1] Implement `app/services/var/exposures.py`: `PositionExposure` and `Exposure` dataclasses (data-model.md) and `build_exposures(ladder_df, lookup: Callable[[str], IdentifierMappingEntry | None]) -> dict[date, Exposure]`, with `fingerprint` left as `""` until US5. Makes T019 pass.
- [X] T023 [US1] Implement `app/services/var/engine.py`:
  - `rank_k`, using integer `ceil_div`;
  - `var_es`, using `fractions.Fraction` for m and returning GBP floats;
  - `scenario_pnl(returns_matrix, values)`;
  - `estimate(exposure, panel, as_of_row, lookback_days, confidences_bp, settings) -> VarEstimate`: window rows; observed-share exclusion using the instrument's own `observed` mask; rescale for NaN cells (value-weighted mean of present positions); coverage classes (actual / rescaled only in US1); quality via thresholds (`insufficient` stores a reason and no VaR/ES);
  - `estimate_all_lookbacks(...)`, reusing one window for every look-back as tail slices.
  Makes T017 pass.
- [X] T024 [US1] Add a `_get_var_run_service(...)` dependency factory in `app/api/risk_var.py`. It wires `VarRunService` from `get_ladder_repository`, `get_capital_repository` (→ `AccountsService`), the identifier mapping repository (reuse `_get_identifier_mapping_repository` from `app/api/ladder.py`), `get_observed_price_client`, `get_var_repository`, `get_run_scheduler` and `get_settings().var`.
- [X] T025 [US1] Implement `VarRunService` in `app/services/var/var_run_service.py`:
  - `create_run(account_name, request, today, correlation_id)` (validation per data-model.md: account exists via `AccountsService`, has a ladder; writes a `queued` record that stores `correlation_id`; submits `execute(run_id)` to the scheduler; returns the `VarRun`);
  - inside `execute`, bind `run_id`, `account_name` and the stored `correlation_id` with `structlog.contextvars.bound_contextvars` for the whole job;
  - `execute(account_name, run_id)` with stages load_ladder → select_dates (`full`: every ladder date in range) → fetch_prices (one `get_observed_price_history` per identifier over research.md §8's range) → build_panel → compute (every date × look-back) → persist (`VarRepository.commit`).
  It marks the run `running`, then `succeeded` with counts, and logs `var_run_stage` durations. Failure handling comes in US2. Collaborators are injected: `LadderRepository`, `AccountsService`, `IdentifierMappingRepository`, `ObservedPriceClient`, `VarRepository`, `RunScheduler`, `VarSettings`.
- [X] T026 [US1] Add `POST /v1/accounts/{account_name}/risk/var/runs` (202, body `VarRun`, `Location` header = `_links.self`) and `GET /v1/accounts/{account_name}/risk/var/runs/{run_id}` in `app/api/risk_var.py`, using the T024 factory. Pass the request's correlation ID (from structlog contextvars) to `create_run`. Validate the account name with `validate_account_name`. Parse the body as an optional dict and validate it in-handler with `VarRunRequest.model_validate`, converting a `ValidationError` into `InvalidVarRunRequestError` (research.md §10). Makes the T020 scenarios pass.

**Checkpoint**: The US1 BDD scenarios and engine, panel and exposure unit tests pass; a `full` run populates `estimates.csv`.

---

## Phase 4: User Story 2 - Start a Calculation Run and Follow Its Progress (Priority: P1)

**Goal**: A robust run lifecycle: one active run per account (409), serial execution, failures
recorded with no partial writes, interrupted runs recovered, runs listed, invalid requests rejected
in RFC 7807 format.

**Independent Test**: POST a run and poll it to `succeeded`; POST twice for a 409; break market data
for `failed` with no store change; restart (call the lifespan recovery) to turn `running` into
`failed(interrupted)`.

### Tests for User Story 2 (write first, must fail) ⚠️

- [X] T027 [P] [US2] Write unit tests in `tests/unit/test_var_run_service.py`:
  - `create_run` raises `VarRunInProgressError` when a `queued` or `running` record exists for the account, but not for another account's;
  - two threads calling `create_run` concurrently (with a scheduler that never runs jobs) produce exactly one run and one conflict;
  - `execute` with the observed client raising `MarketDataServiceError` → run `failed` with reason `market_data_unavailable` and the store untouched;
  - with `ObservedHistoryUnsupportedError` → reason `observed_history_unsupported`;
  - any other exception → `internal_error`, with the run never left `running`;
  - every `RunFailure` carries the run's `run_id` and the creating request's `correlation_id`;
  - `recover_interrupted()` rewrites every `queued` and `running` record across accounts to `failed`/`interrupted` with `finished_at` set, and leaves succeeded/failed records alone;
  - a requested range is clipped to the ladder range, and a range with no ladder dates succeeds with 0 dates computed.
- [X] T028 [P] [US2] Add the US2 scenarios from spec.md (immediate acknowledgement, finished run reports outcome, one active run per account, runs execute one at a time, failed run records why, interrupted runs, invalid run requests) to `tests/features/var_calculation_runs.feature`, with steps in `tests/steps/var_calculation_runs_steps.py`:
  - for "one active run", seed a `queued` run record directly via `VarRepository.write_run` before POSTing;
  - for "one at a time", call `ThreadRunScheduler` directly with two `VarRunService.execute` jobs for two accounts and compare the stored `started_at`/`finished_at`;
  - for "interrupted", seed a `running` record and call the app's startup recovery.
- [X] T029 [P] [US2] Write `tests/unit/test_risk_var_openapi.py`: `app.openapi()` contains the POST/GET runs and GET run paths, a 202 response for POST, the 409/404/422 responses, and `_links`, `correlation_id` and `dates_skipped` properties on `VarRun`.

### Implementation for User Story 2

- [X] T030 [US2] In `app/services/var/var_run_service.py`:
  - add a module-level `threading.Lock` around the "check active → write queued record" section of `create_run` (research.md §3);
  - wrap `execute` in try/except mapping `MarketDataServiceError` → `market_data_unavailable`, `ObservedHistoryUnsupportedError` → `observed_history_unsupported`, and any `Exception` → `internal_error`;
  - record `RunFailure` (type/title/detail/reason/run_id/correlation_id) with `finished_at`, and log `var_run_failed` via `logger.exception`, so the stack trace goes to the logs but never into the payload;
  - commit to the store only in the final persist stage, so a failure never writes partial results;
  - implement `recover_interrupted(repo)`, logging `var_run_interrupted` per record.
- [X] T031 [US2] Add `GET /v1/accounts/{account_name}/risk/var/runs` (query `limit`, default 20, 1..100, validated in-handler → `InvalidVarRunRequestError`) returning `VarRunList` with `_links`. Ensure every `VarRun` response carries `_links.self`, `_links.account_runs` and `_links.status`. File: `app/api/risk_var.py`.
- [X] T032 [US2] In the `app/main.py` lifespan, call `VarRunService.recover_interrupted` (via a `VarRepository` built from settings) after the data directory is ensured, and call `get_default_scheduler().shutdown()` on shutdown. Expose recovery as a plain function (e.g. `recover_interrupted_runs(settings)`) so the BDD step from T028 can invoke it without restarting the app.

**Checkpoint**: The US1 + US2 BDD scenarios pass; this is a usable MVP (full runs only, actual returns + rescale).

---

## Phase 5: User Story 3 - Handle Instruments With Short or Sparse Price History (Priority: P2)

**Goal**: Proxy `fill_gaps`/`always` with scale, sparse detection, rescale after a missing proxy,
coverage percentages (actual/proxied/rescaled) and quality flags.

**Independent Test**: Configure a short-history instrument with a proxy at scale 1.5, run, and verify
the pre-inception scenario returns equal 1.5 × the proxy's and that coverage and quality are correct.

### Tests for User Story 3 (write first, must fail) ⚠️

- [X] T033 [P] [US3] Add engine unit tests to `tests/unit/test_var_engine.py`:
  - `fill_gaps` proxy with scale 1.5 turns a proxy −2% into −3% before inception, with actual returns after;
  - `always` uses the proxy on every row;
  - density < 0.8 in the window triggers `always` when a proxy exists, and rescales the whole window when none does. Density is measured only over window days on or after `first_observed`: an instrument with 260 days of daily prices in a 1300-day window is **not** sparse, keeps its actual returns for those 260 days, and is proxied or rescaled only before its first price (FR-010, U1);
  - scenario exclusion counts a proxied cell as observed when the **proxy** was observed that day: a window where 60% of risky value is proxied (with the proxies observed) keeps all its rows, and rescaled cells never count as observed (FR-004, A1);
  - a proxy NaN on a row falls back to rescale for that row;
  - coverage precedence (rescaled > proxied > actual) and percentages over risky value;
  - quality thresholds: 70/26/4 → degraded; n < 0.8·L → insufficient with reason; rescaled 23% → insufficient; rescaled 5% and proxied 25% → ok (boundaries inclusive as in FR-013).
- [X] T034 [P] [US3] Add the US3 scenarios from spec.md to `tests/features/var_calculation_runs.feature`, with steps in `tests/steps/var_calculation_runs_steps.py`. Use `fake_identifier_mapping_repository.set_entry(..., var_proxy=..., var_proxy_mode=..., var_proxy_scale=...)` and configure the proxy's observed prices.
- [X] T035 [P] [US3] Add a unit test to `tests/unit/test_var_run_service.py`: a proxy identifier that market-data reports as 404 produces a `proxy_unresolved` warning and is treated as having no proxy; a held identifier that is 404 produces `instrument_not_found` and is rescaled.

### Implementation for User Story 3

- [X] T036 [US3] Add a `ProxyConfig` dataclass and `build_proxy_configs(entries) -> dict[str, ProxyConfig]` (keyed by held identifier) to `app/services/var/exposures.py`.
- [X] T037 [US3] Extend `estimate` in `app/services/var/engine.py` with per-window, per-position treatment selection (research.md §6 steps 3–5):
  - proxy substitution with scale;
  - density-based `always`, with density over days on or after `first_observed`;
  - proxy-missing → rescale;
  - the PROXY provenance code;
  - a `source_observed` mask (own observation for ACTUAL, the proxy's for PROXY, False for RESCALE) now feeding the scenario-exclusion rule in place of the US1 own-observation mask;
  - `proxied_mv_pct` and full quality evaluation.
  Makes T033 pass.
- [X] T038 [US3] In `app/services/var/var_run_service.py`: fetch proxy identifiers' observed histories alongside held ones (deduplicated); add proxies to the panel; translate `InstrumentNotFoundError` into the warnings from T035; and pass the proxy configs to the engine. Makes the T034 and T035 tests pass.

**Checkpoint**: US1–US3 pass independently; estimates carry correct coverage and quality.

---

## Phase 6: User Story 4 - Record the Realised Outcome Against Each Estimate (Priority: P2)

**Goal**: Store the outcome date, hypothetical PnL and ladder PnL per as-of date. The newest date is
pending, and a later run fills it.

**Independent Test**: Two consecutive seeded days; verify hypothetical PnL 0 GBP and ladder PnL
−500 GBP for the spec's figures; verify the last ladder date is pending.

### Tests for User Story 4 (write first, must fail) ⚠️

- [X] T039 [P] [US4] Add unit tests to `tests/unit/test_var_engine.py` for `hypothetical_pnl(exposure, panel, outcome_row)`: A 60000 at +1% and B 30000 at −2% → 0; an instrument not observed on the outcome day contributes 0; Cash contributes 0.
- [X] T040 [P] [US4] Add the US4 scenarios from spec.md to `tests/features/var_calculation_runs.feature`, with steps in `tests/steps/var_calculation_runs_steps.py`. For ladder PnL, assert equality with `compute_daily_portfolio_return(...)` at the outcome date × the as-of total value. For "filled later", ingest a ladder extended by one business day (rewrite `ladder.xlsx`/`meta.json` via `LadderRepository.write`) and run `full` (US5 will make `missing` work).

### Implementation for User Story 4

- [X] T041 [US4] Implement `hypothetical_pnl` in `app/services/var/engine.py`, making T039 pass.
- [X] T042 [US4] In `app/services/var/var_run_service.py`, compute outcomes for every selected date:
  - `outcome_date = as_of + BDay(1)`;
  - pending (null PnLs, `outcome_status = "pending"`) when after the ladder's `to_date`;
  - otherwise `hypothetical_pnl`, and `ladder_pnl = compute_daily_portfolio_return(ladder_df, ladder_from, ladder_to)` daily return at the outcome date × `exposure.total_value`;
  - extend the price-fetch range to include the outcome days;
  - write `outcomes.csv` rows through `VarRepository.commit`.
  Makes T040 pass.

**Checkpoint**: Outcomes stored; the newest date is pending.

---

## Phase 7: User Story 5 - Recompute Only What Is Missing or Out of Date (Priority: P2)

**Goal**: Per-date fingerprints; a `missing` run selects dates that are missing, stale (fingerprint
mismatch) or pending-now-resolvable; a requested range restricts the selection.

**Independent Test**: Run `full`, then `missing` → 0 computed. Re-price one date → only that date
recomputes. Change the config → every date recomputes.

### Tests for User Story 5 (write first, must fail) ⚠️

- [X] T043 [P] [US5] Write `tests/unit/test_var_fingerprint.py`:
  - the same inputs give the same hash regardless of position order;
  - a market value change in the 3rd decimal place does **not** change it (rounded to pence) but a 1p change does;
  - a change to methodology version, any `VarSettings` field, or any proxy field changes it.
- [X] T044 [P] [US5] Add date-selection unit tests to `tests/unit/test_var_run_service.py` for a `select_dates(mode, ladder_dates, stored_outcomes, fingerprints, ladder_to, range)` function:
  - `missing` picks absent dates, mismatched fingerprints, and pending outcomes whose outcome date ≤ `ladder_to`;
  - `full` picks every date in range;
  - the range filter applies to both modes;
  - the counts `dates_missing`, `dates_stale`, `outcomes_pending_filled` and `dates_skipped` (in-range ladder dates not selected) are correct;
  - `execute` with zero dates selected never calls the observed-price client and succeeds with `dates_computed = 0` (SC-004 early exit).
- [X] T045 [P] [US5] Add the US5 scenarios from spec.md to `tests/features/var_calculation_runs.feature`, with steps in `tests/steps/var_calculation_runs_steps.py`. For re-pricing, rewrite one date's `market_value` in the stored ladder; for a config change, override `Settings.var.methodology_version`.

### Implementation for User Story 5

- [X] T046 [US5] Implement `app/services/var/fingerprint.py`: `config_fingerprint(var_settings, proxy_configs) -> str` and `row_fingerprint(config_fp, exposure) -> str` (canonical JSON with `sort_keys=True` → sha256 hex), per research.md §8. Set `Exposure.fingerprint` in `build_exposures` (or immediately afterwards in the run service). Makes T043 pass.
- [X] T047 [US5] Implement `select_dates` and use it in `VarRunService.execute`. Restrict computation and the price-fetch range to the selected dates; when nothing is selected, skip the fetch_prices, build_panel, compute and persist stages and succeed immediately (research.md §8 early exit). Record `dates_skipped` on the run. Store `row_fingerprint` on outcome and estimate rows. Record the selection counts on the run. Write `meta.json` (`methodology_version`, `config_fingerprint`, `last_successful_run_id`, `updated_at`). File: `app/services/var/var_run_service.py`. Makes T044 and T045 pass.

**Checkpoint**: A `missing` run is incremental and a no-op when nothing has changed.

---

## Phase 8: User Story 6 - See Calculation Coverage, Freshness and Data Warnings (Priority: P3)

**Goal**: The status endpoint, outlier warnings, and an exclusion list for bad prices.

**Independent Test**: After a run with a proxied instrument and a +40% return, `GET …/risk/var/status` reports ranges, counts, the last run, per-instrument treatments and the outlier warning; excluding that price makes the instrument use its proxy that day.

### Tests for User Story 6 (write first, must fail) ⚠️

- [X] T048 [P] [US6] Add to `tests/unit/test_var_return_panel.py`: `find_outliers(panel, threshold)` lists (identifier, date, return) for |r| > 0.25, and not at exactly 0.25; `apply_exclusions(panel, exclusions)` sets the cell to NaN and `observed` to False, and records an `excluded_price` warning for each exclusion that matched.
- [X] T049 [P] [US6] Write `tests/unit/test_var_status_service.py`:
  - status for an account with a ladder but no VaR data → `computed_range` null, `missing_dates` = ladder business-day count, `last_run` null, empty instruments;
  - after a stored run → ladder range from `meta.json`, computed range from `outcomes.csv`, missing = ladder business days without outcome rows, `pending_outcomes` count, `stale_dates_last_run` from the last successful run's `dates_stale`, instruments from `instruments.csv` with `treatment_by_lookback` keyed by look-back code, and warnings from the last successful run;
  - the ladder `.xlsx` is never opened (assert `LadderRepository.read_full_df` is not called).
- [X] T050 [P] [US6] Add the US6 scenarios from spec.md to `tests/features/var_calculation_runs.feature`, with steps in `tests/steps/var_calculation_runs_steps.py`.

### Implementation for User Story 6

- [X] T051 [US6] Implement `find_outliers` and `apply_exclusions` in `app/services/var/return_panel.py` (making T048 pass). Call them in `VarRunService.execute`: exclusions before computing; outliers as warnings, logged with `var_outlier_detected`.
- [X] T052 [US6] In `app/services/var/var_run_service.py`, build and persist `instruments.csv` rows: identifier, sub-accounts, first/last observed dates, proxy settings, treatment per look-back at the latest computed date, and outlier count.
- [X] T053 [US6] Implement `VarStatusService` in `app/services/var/var_status_service.py` per research.md §11 (making T049 pass), and add `GET /v1/accounts/{account_name}/risk/var/status` in `app/api/risk_var.py`. Apply the same account validation and errors as the runs endpoints, return `_links` `self`/`runs`/`account`, and log `var_status_request`.

**Checkpoint**: The status endpoint and data-hygiene features work; US1–US6 BDD scenarios pass.

---

## Phase 9: User Story 7 - Refresh VaR From the Pipeline Scripts (Priority: P3)

**Goal**: A standalone `refresh-var.ps1` script and Phase 7 in `run_end_to_end.ps1`, per contracts/scripts.md.

**Independent Test**: Quickstart steps 5 and 7 (manual; see Complexity Tracking in plan.md).

- [X] T054 [US7] Create (repo root) `scripts/VarRefresh.psm1` exporting `Invoke-VarRefresh -BaseUrl -AccountName -Mode -TimeoutMinutes -PollSeconds -LogFunction`. It POSTs the run, adopts `_links.active_run` on 409, polls `GET` the run until `succeeded`/`failed` or timeout, and returns an object with Account, Status, DatesComputed, WarningCount, Warnings (first 5) and FailureDetail.
- [X] T055 [US7] Create (repo root) `refresh-var.ps1` with the parameters and defaults in contracts/scripts.md. It resolves accounts from `GET /v1/accounts` (those with `position_ladder`) when `-Accounts` is omitted, imports `scripts/VarRefresh.psm1`, refreshes the accounts sequentially, prints a summary table, and exits 1 if any failed or timed out, else 0.
- [X] T056 [US7] Modify (repo root) `run_end_to_end.ps1`:
  - insert `Write-PhaseHeader 7 "Compute Value at Risk"` after Phase 6;
  - for each successfully ingested `$SubAccountLedgers` account, call `Invoke-VarRefresh` (mode `missing`, 15-minute timeout), logging through `Write-Log` (OK/Warn/Error levels) and setting `$OverallSuccess = $false` on failure;
  - renumber the browser phase to `Write-PhaseHeader 8`;
  - update the script's header comment listing the phases.
- [X] T057 [US7] Manually validate quickstart steps 5 and 7 against the running services, and record the outcome (accounts, dates computed, exit code) as a note at the end of `specs/012-var-calculation-runs/quickstart.md`.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T058 [P] Update `README.md`:
  - capability table rows for the VaR runs and status endpoints;
  - a "Risk — VaR calculation runs" Key Behaviours paragraph (modes, 409, background execution, store layout, interrupted recovery, fail-closed on market-data without observed history);
  - the `var:` config block;
  - the proxy fields for the identifier mapping;
  - the new error types in the error table;
  - the new files in File Structure.
- [X] T059 [P] Update `docs/proposals/value-at-risk.md`: set §11-B to "Specified/implemented as 012", and note any deviation made during implementation. Add a follow-up entry to the proposal's §11 later-features table: "add `correlation_id` to all existing problem responses" (the inherited Principle IV gap from plan.md's Complexity Tracking). In the PR description, list both Complexity Tracking deviations (the inherited correlation-ID gap and the untested PowerShell scripts) for the reviewer's Constitution Check.
- [X] T060 Performance check (SC-002/003/004/007), with a `pytest -m performance`-style test in `tests/unit/test_performance.py` following the existing style:
  - a synthetic ladder of 2,700 dates × 50 positions with an in-memory fake observed client;
  - assert a `full` run completes in < 60 s;
  - assert a following `missing` run computes 0 dates in < 15 s;
  - assert POST returns in < 1 s with a scheduler that defers execution;
  - assert status returns in < 2 s.
- [X] T061 Run the quality gates and fix all findings: `ruff check app/ tests/`, `ruff format app/ tests/`, `mypy --strict app/`, `pytest`. Allow only the documented pre-existing flaky `test_idempotent_resubmit_within_1_second` to fail.
- [X] T062 Live validation (memory lesson from feature 004: real data catches what unit tests miss). Once market-data feature 009 is available:
  - run quickstart steps 1–4 against the real HL-ISA and HL-SIPP data;
  - sanity-check VaR99 ≥ VaR97.5 ≥ VaR95, ES ≥ VaR, the latest 2Y quality, and the proxied share;
  - confirm Lindsell Train D Acc shows `2y: proxied` once its proxy is configured.
  If 009 is not yet available, run step 1 and confirm the run fails with `observed_history_unsupported`, then record that outcome.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; blocks all stories.
- **US1 (Phase 3)**: depends on Foundational. **US2 (Phase 4)**: depends on US1 (it hardens the run service and endpoints US1 creates).
- **US3, US4, US5 (Phases 5–7)**: each depends on US1 (engine + run service). They touch the same files (`engine.py`, `var_run_service.py`), so do them **sequentially in priority order**: US3 → US4 → US5.
- **US6 (Phase 8)**: depends on US1 (status reads the store), and gives fuller output after US3/US5 (treatments, stale counts).
- **US7 (Phase 9)**: depends on US2 (409 adoption, run polling); independent of US3–US6.
- **Polish (Phase 10)**: after all desired stories.

### Within each story

Tests (must fail) → pure functions (engine/panel/exposures/fingerprint) → run-service orchestration → endpoints → BDD green.

### Story completion order

```
Setup → Foundational → US1 → US2 ─┬→ US3 → US4 → US5 → US6 → Polish
                                  └→ US7 (can proceed in parallel with US3–US6)
```

## Parallel Opportunities

- **Phase 1**: T002, T004, T005 and T006 (different files).
- **Phase 2 tests**: T007, T008 and T009 together. Implementation: T010, T012 and T013 in parallel once their tests exist; T011 after T010.
- **US1**: tests T017, T018, T019 and T020 together; then T021 and T022 in parallel; T023 after T021/T022; T024 → T025 → T026.
- **US2**: T027, T028 and T029 together.
- **US3–US6**: each story's test tasks marked [P] together.
- **US7** (T054–T056) can be done by a second developer while US3–US6 proceed.
- **Polish**: T058 and T059 together.

### Parallel example: User Story 1

```text
Task: "T017 engine unit tests in tests/unit/test_var_engine.py"
Task: "T018 return-panel unit tests in tests/unit/test_var_return_panel.py"
Task: "T019 exposure unit tests in tests/unit/test_var_exposures.py"
Task: "T020 US1 BDD scenarios in tests/features/var_calculation_runs.feature"
# then
Task: "T021 return_panel.py"   Task: "T022 exposures.py"
```

## Implementation Strategy

### MVP (US1 + US2)

1. Phases 1–2 (setup, foundational).
2. US1: correct VaR/ES from actual returns (rescale for gaps) via `full` runs.
3. US2: safe lifecycle (409, failures, recovery, list).
4. **Stop and validate**: with fakes this is fully testable now. Against real data it needs
   market-data feature 009; without it, runs fail closed with `observed_history_unsupported`.

### Incremental delivery

- **+US3**: proxies make 2Y/5Y trustworthy for short-history instruments (Scottish Widows, Lindsell Train D Acc).
- **+US4**: realised outcomes unblock feature 013 (backtesting) and feature 026 (chart).
- **+US5**: cheap daily refreshes.
- **+US6**: status for the UI and for diagnostics.
- **+US7**: pipeline automation.

## Notes

- [P] tasks touch different files with no dependency on incomplete tasks.
- Verify each test fails before implementing it (Principle I).
- Commit after each task or logical group (`/speckit-git-commit` hooks are available).
- Total: 62 tasks. Setup 6 · Foundational 10 · US1 10 · US2 6 · US3 6 · US4 4 · US5 5 · US6 6 · US7 4 · Polish 5.
