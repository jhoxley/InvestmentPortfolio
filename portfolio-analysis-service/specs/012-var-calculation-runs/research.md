# Research: Historical-Simulation VaR Calculation Runs

The Technical Context has no `NEEDS CLARIFICATION` markers left. Methodology choices come from
`docs/proposals/value-at-risk.md` (§3, §5) and were confirmed in the spec. The decisions below
resolve the design questions the spec leaves to planning.

## 1. Getting observed-only prices, and failing closed

**Decision**: Add a new, narrow protocol `ObservedPriceClient` with one method,
`get_observed_price_history(identifier, from_date, to_date, currency) -> ObservedPriceHistory`.
`ObservedPriceHistory` holds `points: list[PriceHistoryPoint]`, `first_observed_date: date | None`
and `last_observed_date: date | None`. `HttpMarketDataClient` implements it by calling
`GET /securities/{id}/history?...&fill=none`. If the response **lacks** `first_observed_date`
(market-data without feature 009), it raises `ObservedHistoryUnsupportedError`.

**Rationale**: FastAPI ignores unknown query parameters, so an older market-data service would quietly
return gap-filled prices for `fill=none`. Checking for the new response field is the only reliable
way to detect support, and it lets the run fail closed (FR-026). A separate protocol keeps
`PricingEnrichmentService`'s `MarketDataClient` dependency unchanged (Interface Segregation).

**Alternatives considered**: Adding a method to the existing `MarketDataClient` protocol was rejected
because every ladder-pricing fake would have to implement it. Detecting fills heuristically was
rejected by decision D2.

**404 handling**: an identifier market-data can't price (404) raises `InstrumentNotFoundError`. For a
held instrument that becomes an instrument with no history (rescale, plus a warning). For a proxy it
means "no proxy" (plus a warning). Other non-2xx responses, timeouts and connection errors raise
`MarketDataServiceError` and fail the run.

## 2. Background execution and "one at a time"

**Decision**: A `RunScheduler` protocol with `submit(job: Callable[[], None]) -> None`. The
production `ThreadRunScheduler` wraps one process-wide `ThreadPoolExecutor(max_workers=1)`. It is
created lazily, exposed through a FastAPI dependency (`get_run_scheduler`), and shut down in the
app lifespan. Tests override the dependency with `InlineRunScheduler`, which runs the job
synchronously.

**Rationale**: A single worker serialises runs across all accounts in submission order (FR-018) with
no extra infrastructure. The `max_workers=1` FIFO queue is the run queue. The protocol keeps tests
deterministic.

**Alternatives considered**:
- FastAPI `BackgroundTasks`: runs concurrently across requests, so it can't serialise, and
  TestClient blocks on it anyway.
- An external queue (Celery, RQ): a new dependency and process, unjustified for a local single-user
  service.
- `asyncio` tasks: the calculation is CPU- and pandas-bound and would block the event loop.

## 3. Admission control (409) without races

**Decision**: `VarRunService.create_run()` holds a module-level `threading.Lock` while it:
1. reads the account's run records,
2. rejects with `VarRunInProgressError` if any is `queued` or `running`,
3. writes the new `queued` record.

Only then does it submit the job. The job flips the record to `running` and finally to `succeeded`
or `failed`.

**Rationale**: Two near-simultaneous POSTs can't both pass the check. Run records on disk are the
single source of truth, which also serves start-up recovery (§4) and the runs list.

## 4. Interrupted runs

**Decision**: At start-up the app lifespan calls `VarRunService.recover_interrupted()`. It scans
`data/*/var/runs/*.json` and rewrites every `queued` or `running` record as `failed` with
`failure.reason = "interrupted"` (FR-024).

**Rationale**: `uvicorn --reload` and service restarts kill the worker thread, and the queue lives
only in memory, so any queued or running record at start-up is orphaned by definition.

## 5. Store format and "all or none" writes

**Decision**: Per account, under `data/{account}/var/`:
- `estimates.csv`: one row per (date, lookback_days)
- `outcomes.csv`: one row per date
- `instruments.csv`: per-instrument treatment from the last successful run
- `meta.json`: methodology version, config fingerprint, last successful run id, updated time.
  The stale count is read from that run's record (`dates_stale`), not duplicated here.
- `runs/{run_id}.json`

A run builds the complete new contents of the three CSVs and `meta.json` in memory (existing rows
minus recomputed keys, plus new rows, sorted). It writes each to a temp file in the same directory,
and only after **all** temp files exist does it `os.replace` them in turn. `meta.json` goes last.
Any exception before the replace phase deletes the temp files and leaves the store untouched.

**Rationale**: This matches `LadderRepository`'s temp-file-then-rename pattern. The only exposure is
the microseconds between successive renames, which is acceptable for a single-writer local service
(runs are serialised). CSV keeps the store human-readable with no new dependency. About 8,100
estimate rows per account read in tens of milliseconds.

**Alternatives considered**: Parquet (needs `pyarrow`, a new dependency; volumes don't need it).
SQLite (transactional, but less inspectable, and a departure from the existing file store). A
versioned-directory swap (true atomicity, but more machinery than this needs).

## 6. Engine structure: vectorised and pure

**Decision**: Do the maths in pure functions over numpy arrays, in a new `app/services/var/`
package.

- `ReturnPanel`: business-day grid `D` (length T), identifiers (m), and the arrays
  `returns[T, m]` (float, NaN = missing), `observed[T, m]` (bool) and
  `first_observed[m]`.
  - Grid return = price ratio to the instrument's previous observed price on observed days, 0.0 on
    unobserved days inside the history, NaN before the first observed price.
  - The first observed day's own return is NaN (FR edge case).
  - Excluded (identifier, date) cells are set to NaN with `observed = False`.
- **Per as-of date t** (all look-backs, one pass):
  1. Holdings vector `v` over positions, with position → identifier column index.
  2. Window rows for the largest look-back. Each smaller look-back is the tail slice of the same
     rows, so "the same scenarios" holds by construction.
  3. Per window and position, choose a treatment:
     - `always` if the mode is `always`, or the instrument is **sparse** in that window (when a
       proxy exists). Sparse means observed days ÷ window business days **on or after
       `first_observed`** is below 0.8. Days before the first price are short history, not
       sparseness, so an instrument with 1Y of daily prices in a 5Y window is **not** sparse.
       If `first_observed` is after the window's end, density is undefined and the instrument is
       simply missing (proxy or rescale).
     - otherwise `fill_gaps` (actual where present, scaled proxy where NaN).
     A sparse instrument without a proxy is rescaled for the whole window (FR-010).
  4. Build `R[n, positions]`, a provenance code array (ACTUAL / PROXY / RESCALE), and a per-cell
     `source_observed[n, positions]` mask: ACTUAL cells take the instrument's own `observed`,
     PROXY cells take the **proxy's** `observed`, RESCALE cells are False.
  5. Scenario exclusion: `observed_share[s] = (source_observed[s, :] @ v) / v.sum()` < 0.5 → drop
     row s (FR-004). Because the mask follows the source actually used, heavily proxied windows
     don't lose valid scenario days. Exclusion runs before rescaling, which never adds observation.
  6. Rescale: for each row, positions still NaN take `nanmean` weighted by `v` over the positions
     present (FR-011). If none are present, the row was already excluded by (5).
  7. `pnl = R @ v`; `losses = -pnl`; VaR and ES by the rank formulas.
- `rank_k(n, p_bp) = n - ceil_div(n * p_bp, 10_000) + 1` with integer `ceil_div`. `p_bp` is in
  {9500, 9750, 9900}.
- ES uses exact rational `m = n * (10_000 - p_bp) / 10_000` via `fractions.Fraction` for the
  floor and the fractional weight, so ES at n = 520, p = 0.99 uses m = 26/5 exactly.

**Rationale**: The prototype benchmark (proposal §2.3) ran about 2,700 dates × 50 instruments × 3
look-backs in 0.58 s with this shape. Pure functions are trivially unit-testable against the
spec's hand-calculated cases (SC-001), and the scenario × position matrix is the seam later
Incremental VaR needs (proposal §8).

**Alternatives considered**: Building pandas frames per date was rejected (around 100× slower).
Interpolated quantiles (numpy `linear`) were rejected because the spec fixes the order-statistic
definition.

## 7. Coverage percentages and quality

**Decision**: Per (date, look-back), each position takes one class:
- `rescaled` if any of its retained scenario rows used RESCALE,
- else `proxied` if any used PROXY,
- else `actual`.

The percentage is the sum of class market values over risky market value × 100. Quality uses the
configured thresholds: insufficient if `n < 0.8·L` or rescaled > 20%; else degraded if rescaled > 5%
or proxied > 25%; else ok. An "insufficient" estimate stores a reason, e.g.
`scenario_count 380 < 416 (80% of 520)` or `rescaled 23.4% > 20%`. A date with zero risky value
is `ok`, VaR/ES 0, coverage 100% actual (spec edge case).

## 8. Fingerprints and the date selection for "missing"

**Decision**: `row_fingerprint = sha256(canonical JSON)`. The canonical JSON is
`{methodology_version, var_config (lookbacks, confidences, thresholds, exclusions), proxy_config
(sorted mapping of identifier → proxy, mode, scale for every instrument with any proxy field),
holdings: sorted [(identifier, sub_account, round(market_value, 2))]}`. It is stored on each
outcome row (one per date) and copied onto estimate rows.

A `missing` run selects dates in range where:
- no outcome row exists, or
- the outcome row's fingerprint ≠ the freshly computed fingerprint, or
- the outcome is pending and the outcome date ≤ the ladder's `to_date`.

`full` selects every ladder date in range. The selected dates are recomputed entirely: all
look-backs plus the outcome. `dates_skipped` = ladder dates in the run's range that were not
selected.

**Early exit**: if no dates are selected, the run skips the fetch_prices, build_panel, compute and
persist stages and succeeds with `dates_computed = 0`. This keeps a no-op `missing` run to roughly
the ladder read plus fingerprinting (SC-004).

**Rationale**: Holdings changes (re-pricing on refresh, re-ingest) invalidate exactly the affected
dates. Config and methodology changes invalidate everything. Price restatements in the windows are
not detected (documented in the spec's assumptions; `full` is the remedy).

**Price fetch range**: from the first selected date minus (max look-back + 5) business days, to
`min(last selected date's next business day, ladder to_date)`. One call per identifier (held in any
selected date, plus their proxies).

## 9. Realised outcomes

**Decision**:
- **Hypothetical PnL** for as-of t = Σ positions `v_i × r_i(t+1)`, using the observed grid return
  (0.0 when the instrument has no observation on t+1, including before its first price).
- **Ladder PnL** = `compute_daily_portfolio_return(ladder_df, ladder_from, ladder_to)` at t+1 ×
  total market value at t (including Cash). The existing function is reused so the series
  matches the performance endpoints by construction.
- t+1 is the next Mon–Fri day. If it's after the ladder's `to_date`, both are null and
  `outcome_status = "pending"`.

## 10. Request validation without breaking RFC 7807

**Decision**: The POST endpoint takes the body as `dict[str, Any] | None = Body(default=None)` and
validates it inside the handler with `VarRunRequest.model_validate`. A Pydantic `ValidationError`, or
start later than end, is converted to `InvalidVarRunRequestError` (422 problem details).

**Rationale**: The project memory records that FastAPI's native validation bypasses the RFC 7807
handlers (feature 004 lesson). There is no global `RequestValidationError` handler, and adding one
would change the error format of every existing endpoint.

## 11. Ladder access and performance

**Decision**: Each run reads the ladder once with `LadderRepository.read_full_df` (about 7 s for
HL-SIPP). The status endpoint never reads the ladder. It uses `meta.json` for the ladder range,
`estimates.csv` and `outcomes.csv` for the computed range and pending count, and the last run record
for the stale count, so it meets SC-007 (< 2 s).

**Missing-date count in status**: business days in the ladder range (`pd.bdate_range`) minus dates
that have outcome rows. This is the same Mon–Fri grid the ladder uses.

## 12. Configuration

**Decision**: Add a `VarSettings` model under `Settings.var` in `config.py`, with defaults matching
the spec:

```yaml
var:
  methodology_version: "1.0.0"
  lookbacks: {"1y": 260, "2y": 520, "5y": 1300}
  confidence_levels_bp: [9500, 9750, 9900]
  min_observed_share_per_scenario: 0.5
  sparse_density_threshold: 0.8
  outlier_abs_return: 0.25
  quality: {ok_max_rescaled_pct: 5, ok_max_proxied_pct: 25,
            insufficient_min_scenario_ratio: 0.8, insufficient_max_rescaled_pct: 20}
  excluded_returns: []          # [{identifier: "...", date: "YYYY-MM-DD"}]
```

`IdentifierMappingEntry` gains optional `var_proxy: str | None`, `var_proxy_mode: Literal["fill_gaps",
"always"] = "fill_gaps"` and `var_proxy_scale: float = 1.0`. `IdentifierMappingRepository` needs a new
`entries()` method so a run can build the proxy configuration for the fingerprint.

## 13. Scripts

**Decision**: Add a `refresh-var.ps1` at the repository root (beside `run_end_to_end.ps1`) with
`-BaseUrl` (default `http://127.0.0.1:8000`), `-Accounts` (default: every account from
`GET /v1/accounts` that has a position ladder), `-Mode` (`missing`), `-TimeoutMinutes` (15) and
`-PollSeconds` (2). It exits 1 if any run fails or times out.

`run_end_to_end.ps1` gains **Phase 7 "Compute Value at Risk"**, which calls the same polling
function (shared by dot-sourcing `scripts/VarRefresh.psm1` or an equivalent helper function). The
browser launch becomes Phase 8.

**Testing**: PowerShell isn't covered by the pytest suite. The scripts are verified by the
quickstart's manual steps (see Complexity Tracking in plan.md).

## 14a. Correlation IDs on errors and runs (constitution IV, FR-033)

**Decision**:
- The three new exception handlers (`var-run-in-progress`, `var-run-not-found`,
  `invalid-var-run-request`) build their body with a new helper, `_var_problem(...)`, in
  `app/main.py`. It extends the standard fields with `correlation_id`, read from
  `structlog.contextvars.get_contextvars()["correlation_id"]` (bound by the existing request
  middleware).
- `create_run` stores the same correlation ID on the `VarRun` record (`correlation_id`).
- The background job binds `run_id`, `account_name` and that `correlation_id` into its structlog
  context, so every run log line can be traced to the request.
- `RunFailure` carries `run_id` and `correlation_id`.
- Problem bodies are built **without** stack traces. The constitution allows suppression, and the
  logs keep the trace (`logger.exception`).

**Rationale**: Principle IV requires a correlation ID in every error payload. The shared
`ProblemDetail`/`_problem` used by the existing endpoints lacks it. Changing that shared helper would
alter every existing error response and its tests, which is outside this feature's scope. So this
feature complies for everything it adds, and the inherited gap in existing handlers is recorded in
plan.md's Complexity Tracking for a separate fix.

## 14b. mypy `python_version` and numpy's stubs (found during implementation)

**Finding**: `app/services/var/engine.py` and `return_panel.py` are the first production
modules in this service to `import numpy` directly (pandas was imported before, but its
stubs never forced mypy to fully parse numpy's own `.pyi`). numpy 2.5's `__init__.pyi`
uses PEP 695 `type X = Y` alias statements, which mypy only parses under
`python_version >= 3.12`. The project's `pyproject.toml` pinned `[tool.mypy]
python_version = "3.11"`, so `mypy --strict app/` failed outright on a syntax error
inside numpy's stub, unrelated to any code in this feature.

**Fix**: bumped `[tool.mypy] python_version` to `"3.12"`. This only changes what syntax
mypy accepts while *reading installed stubs*; nothing in this codebase uses 3.12-only
syntax, so it has no effect on runtime behaviour, and `[project] requires-python` (the
package's actual floor) is unchanged. Verified: `mypy --strict app/` clean across all 69
source files after the change, full suite (548 tests) green.

## 14. Logging events

`var_run_queued`, `var_run_started`, `var_run_stage` (stage = load_ladder | select_dates |
fetch_prices | build_panel | compute | persist, plus `duration_ms`), `var_instrument_treatment`,
`var_outlier_detected`, `var_proxy_unresolved`, `var_run_succeeded`, `var_run_failed`,
`var_run_interrupted`, and `var_status_request`. Each event carries `account_name` and `run_id`.
