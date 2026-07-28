# Research: Account Performance Retrieval Endpoints

No `NEEDS CLARIFICATION` markers remain in the Technical Context (see plan.md) — this feature
reuses the existing stack (FastAPI, pandas, Pydantic, structlog, pytest/pytest-bdd) with no new
dependencies. The decisions below resolve the design questions the spec deliberately left to
planning.

## 1. Look-back is free — no windowed data fetch needed

**Decision**: `PerformanceService` always reads an account's *entire* stored position ladder via
the existing `LadderRepository.read_full_df()`, computes every performance measure across the
account's *complete* history, and only slices down to the resolved `[start, end]` window as the
final step before building the response.

**Rationale**: `LadderRepository` has no partial/windowed read method — `read_full_df()` already
returns every stored row regardless of any date filter (this is also what
`TimeSeriesService.get_series()` does today for `market_value`). Because trailing/expanding
metrics (FR-006–FR-009) are computed as pandas `rolling`/`expanding` operations over the *entire*
daily-return series before the response window is sliced out, User Story 3's look-back
requirement ("a 3Y return for 2022-01-01 must reach back to 2019-01-01, even though only
2022-01-01 is in the requested window") falls out automatically — there is no separate
"compute the minimum required look-back per requested attribute" step to get wrong. This is
simpler than introducing per-attribute look-back bookkeeping and has no correctness edge cases to
special-case.

**Alternatives considered**: Fetching only `[start - max_lookback, end]` of ladder rows was
rejected — `LadderRepository` has no such partial-read primitive, and introducing one would only
matter for very large ladders, which are out of scope (Scale/Scope below).

## 2. Daily portfolio return: aggregate, then zero-fill gaps (not forward-fill)

**Decision**: Aggregate the ladder to one row per business day
(`ladder_df.groupby("date")["weighted_position_return"].sum()`), then reindex over
`pd.bdate_range(ladder_meta.from_date, resolved_end)` and fill any date with no ladder rows with
`0.0` (not forward-filled from the previous day's value).

**Rationale**: The Key Entities section of the spec defines Daily Portfolio Return as literally
"the sum of `weighted_position_return` across every position present in that day's position
ladder" — for a date with no rows (no position, including "Cash", active that day), the sum over
an empty set is `0.0` by definition, not a repeat of the prior day's return. This differs
deliberately from how `TimeSeriesService` forward-fills `market_value`/`capital` for staleness
(a date after the ladder's last recorded date, before the next refresh): forward-filling a
*value* (market value stays flat) is equivalent to a `0.0` *return* for that same stale period
(no price movement recorded ⇒ no return), so zero-filling the return series and forward-filling
value series are two expressions of the same underlying assumption, not a contradiction.

**Alternatives considered**: Reusing `expand_business_days()` (which forward-fills) directly was
rejected — forward-filling a *return* would repeat a stale non-zero daily return into the
cumulative product for every gap day, silently inflating or deflating every downstream measure.

## 3. Trailing/expanding metrics via pandas `rolling`/`expanding`, using NaN as "not yet computable"

**Decision**: Compute all five measures as full-length pandas Series aligned to the complete
daily-return series (from the ladder's earliest date through the resolved end date):

- `ITD`: `(1 + daily_return).expanding().apply(lambda w: w.prod()) - 1` (always defined from the
  first row onward — the first row's `daily_return` is `0.0` per feature 006's first-trade-date
  rule, so `ITD` on day 1 is exactly `0.0`, matching the spec's edge case).
- `ITD (Ann.)`: `(1 + ITD) ** (260 / elapsed_trading_days) - 1`, where `elapsed_trading_days` is
  the 1-indexed row position since inception (`1, 2, 3, …`).
- `1Y`: `(1 + daily_return).rolling(window=260).apply(lambda w: w.prod()) - 1`, no further scaling.
- `3Y` / `5Y`: the same rolling-window cumulative product over 780 / 1300 days, each then
  annualized as `(1 + windowed_cumprod) ** (1/3 or 1/5) - 1`.

Pandas `rolling(window=N)` defaults to `min_periods=N`, so any date with fewer than `N` preceding
rows in the *real* (non-padded) series produces `NaN` automatically — this is exactly FR-011's
"omit the key" rule, with no extra bookkeeping: a `NaN` value is simply dropped when building that
date's response entry (mirrors how `TimeSeriesEntry`/`PerformanceEntry`'s `extra="allow"` already
omits keys for attributes never present on a row).

**Rationale**: This directly implements the formulas given in the feature description (FR-006
through FR-009) using vectorized, idiomatic pandas — consistent with how `PricingEnrichmentService`
and `ReturnsEnrichmentService` already use vectorized per-group operations rather than row-by-row
Python loops. Because the daily-return series is never zero-padded *before* the ladder's true
first date (only internal gaps are zero-filled, per decision 2), `rolling`'s `NaN` output
correctly reflects "not enough real history", never a false positive from synthetic padding.

**Alternatives considered**: Manually looping over dates and checking `len(available_history) >= N`
before computing each measure was rejected as unnecessary — pandas' own `min_periods` behaviour
already encodes exactly this check.

## 4. Reuse the existing date-resolution and account-lookup services unchanged

**Decision**: `PerformanceService` takes `TimeseriesDateResolver` and `AccountsService` as
constructor dependencies (the exact same classes `TimeSeriesService` already uses) and calls them
identically: `AccountsService.get_summary()` for existence/date-range lookups,
`TimeseriesDateResolver.resolve()` for `start`/`end` defaulting and business-day adjustment.

**Rationale**: FR-004 requires the performance endpoint's defaulting/validation behaviour to be
identical to the existing time series endpoint's — reusing the same two classes guarantees this
by construction rather than by parallel reimplementation (and any future bugfix to date
resolution benefits both endpoints automatically). Both classes are already dependency-free of
any particular attribute set, so no modification to either is needed.

**Alternatives considered**: Duplicating a `PerformanceDateResolver` was rejected as needless
duplication of logic the spec explicitly requires to match exactly.

## 5. Account/source-missing errors reuse existing exception types and handlers

**Decision**: `PerformanceService` raises the existing `AccountNotFoundError` (account has no
ingested resource of any kind) or `MissingRequiredSourceError` (account is known, e.g. via a
capital ledger, but has no position ladder) — the same two exceptions
`TimeSeriesService` raises today. `NoAttributesRequestedError`/`UnsupportedAttributeError` are
raised by a new `performance_attributes.validate_attributes()`, mirroring
`timeseries_attributes.validate_attributes()` exactly. No new FastAPI exception handler is added
to `app/main.py` — all five exception types already have registered handlers producing RFC 7807
responses.

**Rationale**: Since every performance measure requires `position_ladder` and none require
`capital_ledger`, the "required source" logic collapses to a single check (unlike
`TimeSeriesService`, which checks capital vs. ladder independently per attribute) — but the
exception vocabulary and HTTP status mapping (404 vs. 422) are unchanged, satisfying FR-013.

**Alternatives considered**: A new `PerformanceLadderNotIngestedError` was rejected —
`MissingRequiredSourceError` already carries an `attribute`/`source` pair generic enough to name
any performance measure and `"position_ladder"`.

## 6. New, parallel response models rather than reusing `timeseries.py`'s models directly

**Decision**: Add `app/models/performance.py` with `PerformanceEntry`, `PerformanceResponse`,
`PerformanceAttributeDefinition`, and `PerformanceAttributeMetadataResponse` — structurally
identical to `TimeSeriesEntry`/`TimeSeriesResponse`/`AttributeDefinition`/
`AttributeMetadataResponse`, but distinct classes.

**Rationale**: The spec requires the *response shape* (field names or their meaning) to match,
not that the same Python class must be reused. The codebase already has this precedent:
`app/models/position_timeseries.py` (feature 005) defines its own `PositionTimeSeriesEntry`/
`PositionTimeSeriesResponse` rather than reusing `TimeSeriesEntry`/`TimeSeriesResponse`, even
though the shapes overlap heavily. Keeping the performance API's models independent honours
Single Responsibility (per Constitution Principle II): the two attribute universes (raw ledger
figures vs. derived performance ratios) are unrelated domains that would otherwise be coupled by
a shared class, and can now evolve (e.g. more performance measures with extra metadata fields)
without risking a change to the account time series response shape.

**Alternatives considered**: Importing and reusing `TimeSeriesResponse`/`TimeSeriesEntry` directly
was considered (marginally less code) but rejected as inconsistent with the position timeseries
precedent and as introducing an accidental coupling between two independently-evolving APIs.

## 7. Wire-format attribute names are the literal display labels

**Decision**: The `attribute` query parameter values and response entry keys are exactly `ITD`,
`ITD (Ann.)`, `1Y`, `3Y`, and `5Y` — not converted to `snake_case` identifiers.

**Rationale**: The feature description explicitly quotes these five labels as what the endpoint
"will expose"; no alternative machine-friendly naming was given, and standard percent-encoding
(`ITD%20%28Ann.%29`) handles the space/parentheses in a query string and a JSON object key without
issue. This is recorded as an explicit Assumption in spec.md.

**Alternatives considered**: `itd`, `itd_annualized`, `return_1y`, `return_3y`, `return_5y`
(matching the existing `snake_case` convention used by `timeseries_attributes.py`) was considered,
but rejected in favour of the literal, explicitly-requested labels — introducing a translation
layer the user did not ask for would be unjustified scope creep.
