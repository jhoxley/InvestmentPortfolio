# Research: VaR Series, Backtest and Methods Endpoints

All items below resolve design questions raised by the spec; none were left as
`NEEDS CLARIFICATION` in `spec.md` itself (see its Assumptions section), so this file
records *how* each is implemented, not a remaining open choice.

## 1. Date-window resolution without reading the ladder

**Decision**: A new `app/services/var/var_window.py` module exposes
`resolve_window(accounts_service, date_resolver, account_name, start, end, today,
attribute_label) -> WindowResolution` (a small frozen dataclass of `resolved_start`,
`resolved_end`, `ladder_from_date`). It calls `AccountsService.get_summary()` (metadata
only — checksums, row counts, from/to dates, no price or ladder rows) and
`TimeseriesDateResolver.resolve()`, raising the same `AccountNotFoundError` /
`MissingRequiredSourceError` / `FutureEndDateError` / `InvalidDateRangeError` the
performance endpoints raise (FR-002, FR-024).

**Rationale**: `DailyReturnSeriesLoader` (used by the performance and
return-histogram endpoints) does the same account/date validation but then
unconditionally calls `LadderRepository.read_full_df()` to build a return series —
work this feature never needs, since it only reads `estimates.csv`/`outcomes.csv`.
Reusing `DailyReturnSeriesLoader` directly would silently reintroduce the full ladder
read into this endpoint's hot path, violating SC-004's 2-second budget for a 10-year
request under normal load. `VarStatusService` already established the pattern of
calling `AccountsService.get_summary()` directly and never touching
`read_full_df()`; `var_window.py` extracts just the date-resolution half of that
pattern into a shared helper for the two new services.

**Alternatives considered**: (a) Reuse `DailyReturnSeriesLoader.load()` and discard its
`daily_returns` — rejected for the performance reason above. (b) Duplicate the
validation/resolution logic inline in each service — rejected; it is identical for
both endpoints and belongs in one place (SOLID, single responsibility).

## 2. Validating `lookback`, `confidence`, `pnl_basis`, `min_quality`

**Decision**: A new `InvalidVarQueryError` (422, RFC 7807 slug `invalid-var-query`,
`correlation_id` via the existing `_var_problem()` helper) covers all four parameters:
an unsupported `lookback` code, an unsupported `confidence` value (compared as basis
points after parsing `"95"`/`"95%"`/`"0.95"`-style input — see §3), an unsupported
`pnl_basis`, or an unsupported `min_quality`. The message names the supported values for
that parameter, satisfying FR-009/FR-021/SC-006.

**Rationale**: Feature 012's `InvalidVarRunRequestError` is scoped to the run-request
body (`mode`, `start`/`end` ordering) and its message/slug ("Invalid VaR Run Request")
would be misleading reused for query-parameter validation on a GET. A single new type
(rather than four) follows feature 012's own precedent of one validation error type per
endpoint-group concern, and keeps the router/handler pair small.

## 3. Confidence-level query parameter parsing

**Decision**: `confidence` is a repeatable query parameter accepted as a percentage
(`95`, `97.5`, `99`) — matching how confidence levels are already described everywhere
else in this codebase (`VarRunRequest`'s sibling `VarSettings.confidence_levels_bp` is
basis points internally, but every human-facing surface, including the proposal and this
feature's own spec text, speaks of "95%", "97.5%", "99%"). The router converts to basis
points (`round(value * 100)`) before comparing against `VarSettings.confidence_levels_bp`;
an unparsable or unsupported value raises `InvalidVarQueryError` naming the configured
percentages. Omitted entirely → every configured level (FR-004).

**Rationale**: Internal basis-point integers avoid float comparison everywhere else in
the engine; the query boundary is exactly where Pydantic/FastAPI validation belongs
(Principle III — "Pydantic models ... at all external data boundaries"), so the
conversion happens once, at the edge.

## 4. Series endpoint: null handling for `insufficient` quality and pending outcomes

**Decision**: `estimates.csv` rows store `var_95.._gbp`/`es_95.._gbp` as empty for
`quality == "insufficient"` (the engine never computes a value for those rows — see
`engine.py`'s existing behaviour). Read back as `NaN` via pandas, these map to `None` in
`ConfidenceLevelEstimate.var_gbp`/`var_pct`/`es_gbp`/`es_pct` and
`hypothetical_exception`/`ladder_exception` (FR-006). Independently, `outcomes.csv` rows
with `outcome_status == "pending"` (the newest computed date — `var_run_service.py`
already uses this exact value) map `hypothetical_pnl_gbp`/`ladder_pnl_gbp` and both
exception flags to `None` (FR-007), regardless of that date's quality. The row still
appears in the series either way (FR-005, FR-008's "edge cases" in spec.md).

**Rationale**: This is a direct, literal translation of the stored data's own
already-established null conventions (feature 012); no new null-handling policy is
introduced, only exposed.

## 5. Exception definition

**Decision**: For PnL series `s` (hypothetical or ladder) and confidence level with
stored `var_gbp`, the exception indicator is `s_pnl_gbp < -var_gbp` (strict), matching
the proposal §4.3 formula `I = 1{PnL < -VaR}` exactly. `var_gbp` is always stored as a
positive loss amount (per `engine.py`'s existing `VarEsResult` convention), so the
comparison needs no sign juggling beyond the leading `-`.

## 6. Backtest observation set construction

**Decision**: `var_backtest_service.py` builds the observation set as:
1. Read `estimates.csv`/`outcomes.csv`, filter to the resolved date range and requested
   look-back, inner-join on `date` (the estimate's `date` == the outcome's `date`, *not*
   `outcome_date` — an estimate and its own realised outcome share the same `date` key in
   the store; `outcome_date` is the next business day the PnL was realised *on*).
2. Drop rows where `quality == "insufficient"` (no stored VaR to test) — **always**,
   regardless of `min_quality` (FR-011, and spec.md's Edge Cases).
3. Drop rows where `outcome_status == "pending"` (no realised PnL yet) — **always**.
4. Apply `min_quality` (default `"degraded"`, i.e. keep `ok` and `degraded`; `"ok"` keeps
   only `ok`) using the ordering `ok > degraded > insufficient` (already established by
   `VarQualitySettings`'s naming — `insufficient` can never pass this filter anyway after
   step 2, so only `"ok"` vs `"degraded"` is a live choice, matching the spec's
   observation that `min_quality` has "effective default behaviour" once insufficient is
   excluded).
5. Sort by `date` ascending. This ordered, filtered frame is the observation set the
   statistics in `backtest.py` consume for every confidence level requested.

**Rationale**: Steps 2–3 are exactly the spec's Edge Cases paragraph and FR-011, made
concrete against the real stored column names. Joining on `date` (not `outcome_date`)
keeps the lookback-day's own as-of row and its own realised next-day PnL together,
matching §4.2's "each stored row carries `date` and `outcome_date`" framing.

## 7. Christoffersen transition-chain breaks (FR-014)

**Decision**: After building the ordered, filtered observation set (§6) once per
confidence level (its filtered rows can differ per level only through quality — in
practice quality is look-back-scoped, not confidence-scoped, so the observation set is
actually identical across confidence levels within one look-back; only the *exception
indicator* differs per level), `backtest.py`'s `christoffersen_independence()` takes the
ordered list of `(date, indicator)` pairs and counts a transition `n_{I(i-1), I(i)}` for
consecutive list entries `i-1, i` **only when** `date[i]` is exactly the next business
day after `date[i-1]` (`date[i-1] + pandas.offsets.BDay(1) == date[i]`). When a gap
exists (an excluded date fell between them), no transition is counted for that pair —
the chain breaks there, exactly as FR-014 and the spec's worked scenario (day 4/day 6
not consecutive when day 5 is excluded) require.

**Rationale**: The observation set is already date-filtered; business-day adjacency on
the *filtered* sequence is the simplest and only correct way to detect "no excluded date
fell between them" without re-deriving the unfiltered calendar separately.

## 8. Statistics formulas (stdlib-only, per proposal §4.3)

**Decision** — implemented exactly as the proposal specifies, using
`fractions`-free plain floats (unlike the rank/ES engine, these are already real-valued
statistical quantities, not order statistics needing exactness):

- **Kupiec POF**: `hat_pi = x / N`; with the `0 ln 0 = 0` convention via a
  `_log_term(count, prob)` helper that returns `0.0` when `count == 0` regardless of
  `prob` (avoiding `log(0)` when `prob` is also 0, e.g. `hat_pi == 0`):
  `LR_pof = -2*(_log_term(N-x, log(1-alpha)) + _log_term(x, log(alpha))) + 2*(_log_term(N-x, log(1-hat_pi)) + _log_term(x, log(hat_pi)))`.
  `p = math.erfc(math.sqrt(LR_pof / 2))` (the exact χ²₁ survival-function identity).
  Undefined (`None`) when `N == 0`.
- **Christoffersen independence**: counts `n00, n01, n10, n11` from §7's adjacency rule;
  `pi01 = n01/(n00+n01)` if that denominator is nonzero else the term contributes 0 via
  the same `_log_term` convention (and symmetrically for `pi11`); `pi = (n01+n11) /
  (n00+n01+n10+n11)`. `LR_ind` via the analogous log-likelihood difference;
  `p = math.erfc(math.sqrt(LR_ind / 2))`. `None` when there are zero valid transitions
  (e.g. `N < 2`, or every adjacent pair was broken by an exclusion).
- **Conditional coverage**: `LR_cc = LR_pof + LR_ind` when both are defined, else `None`;
  `p = math.exp(-LR_cc / 2)` (the exact χ²₂ survival-function identity).
- **Traffic-light zone**: cumulative binomial `F(x; N, alpha) = sum_{i=0}^{x} C(N,i)
  alpha^i (1-alpha)^(N-i)`, computed via `math.lgamma`-based log-binomial-coefficients
  summed as `math.exp(log_pmf_i)` for numerical stability at `N` up to ~2,700 (research
  for feature 012's proposal already benchmarked this approach at `N=250` and it is
  monotonically stable for larger `N` since each term is computed independently rather
  than via a recurrence that could accumulate error). `green` if `F < 0.95`, `yellow` if
  `F < 0.9999`, `red` otherwise (FR-015). `None` when `N == 0`.
- **VaR stability**: `numpy.std(log_changes, ddof=1)` over the list of
  `ln(var_t / var_{t-1})` for consecutive included dates (§7's adjacency rule) whose
  estimate rows share the same `row_fingerprint` (holdings unchanged, FR-016); `None`
  when fewer than 2 such log-changes exist (consistent with
  `return_histogram.py`'s existing `_MIN_OBS_STD_DEV` precedent for `ddof=1` statistics).
- **Rolling 250-day exception count**: a plain sliding-window sum over the *included*
  observation sequence's indicator list (window = 250, step = 1), one point per date
  from the 250th included date onward (FR-019); empty if fewer than 250 observations
  exist (spec.md Edge Cases).

**Rationale**: These are the proposal's own formulas (§4.3), carried over verbatim; the
only implementation decisions are the zero-count conventions and the numerically stable
binomial evaluation, both already precedented from feature 012's own research.

## 9. Methods endpoint content

**Decision**: `var_methods_service.build_methods_response(settings: VarSettings) ->
VarMethodsResponse` is a pure function of `VarSettings` — no repository, no I/O. It lists
`settings.lookbacks` (code → business days) with `is_headline` set from
`settings.headline_lookback`, `settings.confidence_levels_bp` (returned as basis points;
the OpenAPI schema documents the percentage equivalents), and a fixed, literal `measures`
list naming every field the series and backtest endpoints expose (not derived
dynamically — there is no existing registry of "measures" to introspect, and a static
list is simplest and matches FR-022's "describes ... the measures available").

## 10. New configuration: `headline_lookback`

**Decision**: `VarSettings.headline_lookback: str = "2y"`, with a Pydantic
`model_validator(mode="after")` asserting it is a key of `self.lookbacks` (raising a
`ValueError` at settings-construction time, not a request-time error — a misconfigured
deployment should fail fast at startup, consistent with how `VarSettings` is already
constructed once at app startup and never re-validated per request).

**Rationale**: Matches the Assumptions section's "new, additive configuration value
... existing deployments without it explicitly set continue to work via this default."
