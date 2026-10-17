# Research: Risk Endpoints — Daily Return Histogram

No `NEEDS CLARIFICATION` markers remain in the Technical Context; the feature reuses the existing
stack with no new dependencies. The decisions below resolve design questions left to planning.

## 1. Sharing code with the performance endpoints

**Decision**: Extract the acquisition steps currently inline in `PerformanceService.get_performance`
(account/source existence checks → date resolution → start-before-ladder check → ladder read →
`compute_daily_portfolio_return`) into `DailyReturnSeriesLoader.load(account_name, start, end,
today, attribute_label)`, returning the resolved `(start, end)` and the full daily-return
DataFrame. `PerformanceService` and the new `RiskService` both call it.

**Rationale**: The spec requires the same input data and shared code "where feasible". Copying the
~40 lines of validation would let the two groups drift (e.g. different error handling). The
existing `test_performance_service.py` and `retrieve_performance.feature` pin current behaviour
and guard the refactor.

**Alternatives considered**: Having `RiskService` call `PerformanceService` internals — rejected
(couples risk to performance's attribute vocabulary). Duplicating the logic — rejected (drift).
`MissingRequiredSourceError` requires an `attribute` label; the loader takes it as a parameter
(`attributes[0]` for performance, `"return-histogram"` for risk) so error messages stay accurate.

## 2. Windowing and look-back

**Decision**: The histogram uses only dates within `[resolved_start, resolved_end]` (FR-012); the
loader returns the full series and `RiskService` slices it.

**Rationale**: Unlike trailing performance measures, a histogram has no look-back need. Slicing
after the shared load keeps one code path.

## 3. Business days with no ladder rows

**Decision**: Inherit `compute_daily_portfolio_return`'s behaviour — business days from the
ladder's first date through the resolved end with no ladder rows are `0.0` (not forward-filled),
and therefore count as observations in the 0 bp bucket.

**Rationale**: SC-003 / User Story 3 require the histogram and performance endpoints to agree on
the daily return series. Diverging would create the disagreement the feature exists to avoid.
Ladders are business-day expanded on ingestion, so such gaps are rare (after the ladder's last
row, or dates with no positions).

**Alternatives considered**: Dropping zero-filled days — rejected (breaks consistency; would need
to distinguish "no data" from "zero return" in the shared function).

## 4. Rounding to integer basis points

**Decision**: two steps, implemented as two functions in `return_histogram.py`:

1. `round_half_away_from_zero(bps: pd.Series) -> pd.Series` — `np.sign(x) * np.floor(np.abs(x) + 0.5)`,
   cast to `int`. Do **not** use `Series.round()` (banker's rounding).
2. `to_basis_points(daily_returns: pd.Series) -> pd.Series` — `(daily_returns * 10_000).round(9)`
   then `round_half_away_from_zero`. The 9-decimal pre-round removes binary floating-point noise
   (e.g. `0.00015 * 10_000` is `1.4999999999999998`) so a return that is a decimal half in basis
   points rounds as a human expects (1.5 → 2).

**Rationale**: Matches the spec's edge case (0.5 → 1, -0.5 → -1). Tests exercise
`round_half_away_from_zero` directly on exactly representable values (0.5, 1.5, 2.5, -2.5) and
`to_basis_points` on decimal-style returns (0.00005, 0.00015, 0.00025, -0.00025), so both the
rounding rule and the floating-point pre-round are covered.

**Alternatives considered**: `decimal.Decimal` quantisation — rejected as unnecessary for a
sparse, statistical output.

## 5. Statistics definitions

**Decision** (all computed over the rounded integer bps observations, using pandas):

| Statistic | Method | Null when |
|---|---|---|
| count | number of observations | never (0 allowed) |
| mean | `Series.mean()` | n = 0 |
| median | `Series.median()` | n = 0 |
| mode | smallest of the most frequent buckets | n = 0 |
| std_dev | `Series.std(ddof=1)` (sample) | n < 2 |
| std_dev_bands k=1,2,3 | multiple = k·σ; lower = mean − k·σ; upper = mean + k·σ | n < 2 |
| skewness | `Series.skew()` (adjusted Fisher–Pearson) | n < 3 or σ = 0 |
| kurtosis | `Series.kurt()` (sample excess kurtosis) | n < 4 or σ = 0 |
| minimum / maximum | `min()` / `max()` | n = 0 |

**Rationale**: pandas built-ins are well-defined, already a dependency, and avoid adding scipy.
Excess kurtosis (normal = 0) is the convention risk users expect. NaN/inf are never emitted in
JSON — undefined values serialise as `null`.

## 6. Response shape for the histogram pairs

**Decision**: `histogram` is a JSON array of two-element arrays `[bucket_bps, count]`, sorted by
bucket ascending; typed as `list[tuple[int, int]]` in Pydantic and `prefixItems` in OpenAPI.

**Rationale**: The request asks for "a list of pairs". A JSON object keyed by bucket would force
string keys and give no ordering guarantee, which conflicts with the required sort order.

**Alternatives considered**: `[{"bucket": -25, "count": 1}]` — more self-describing but not what
was requested; can be added later without breaking this shape.

## 7. Endpoint path and router

**Decision**: `GET /v1/accounts/{account_name}/risk/return-histogram` with optional `start` and
`end`, in a new `app/api/risk.py` router tagged "Risk". Later risk endpoints hang off the same
`/risk/` segment and router.

**Rationale**: Mirrors `/accounts/{account_name}/performance` (account-scoped) and matches "a
controller called 'risk'". Start/end defaults are identical to the performance endpoints because
the same date resolver is used.

## 8. Errors

**Decision**: Reuse existing exceptions/handlers only. Empty-window results are **not** an error:
they return `200` with an empty histogram and `count = 0` (User Story 4). Start after end,
future end date, unknown account, missing ladder, bad account name → existing RFC 7807 responses.
