# Phase 0 Research: Account Projection Endpoint

Every decision below implements the contract already pinned in `portfolio-browser`'s
`specs/022-projection-page/contracts/portfolio-analysis-api.md`, `research.md` (#1–#3), and
`data-model.md`. Two places where that pinned contract was under-specified relative to this
service's own established conventions are resolved here, explicitly flagged as such rather than
silently reinterpreted.

## 1. Response shape: reuse `PositionTimeSeriesResponse` exactly

**Decision**: The endpoint returns `PositionTimeSeriesResponse` (`app/models/position_timeseries.py`)
unmodified — no new Pydantic model. `attributes` is always `["market_value"]`. The `position`
field (normally a position name) carries a series label instead: `"Historical"` or one of the
requested return names.

**Rationale**: This is explicit in the pinned browser-side contract, and it means zero new
response-serialization code — `PositionTimeSeriesEntry`'s existing `extra="allow"` already
accepts a bare `market_value` key per entry.

## 2. Return names: reuse `performance_attributes.py`'s exact measure names, not new wire codes

**Decision**: The `return` query parameter accepts the *exact* strings
`performance_attributes.ATTRIBUTE_DEFINITIONS` already defines — `"ITD (Ann.)"`, `"1Y"`, `"3Y"`,
`"5Y"` — excluding plain `"ITD"`. A requested return's name is used verbatim as its series'
`position` label; no separate label-mapping table is introduced.

**Correction to the pinned contract**: `portfolio-browser`'s own research.md (#5) guessed at
lowercase wire codes (`itd_ann`, `1y`, `3y`, `5y`) because it didn't have this service's actual
measure names on hand at the time (they don't exist in that repo). Those names already exist
here, in `performance_attributes.py`, and the existing `/v1/accounts/{account}/performance`
endpoint already accepts them verbatim as its own `attribute` query values (URL-encoded, spaces
and parentheses included — confirmed by reading `performance_attributes.validate_attributes`,
which matches against `SUPPORTED_ATTRIBUTES = frozenset(a.name for a in ATTRIBUTE_DEFINITIONS)`).
Reusing those same strings here — rather than inventing a second, parallel naming scheme this
service would need to translate between — is a direct application of this service's own
Principle II (no duplicated domain logic) and keeps `performance_attributes.py` the single
source of truth for measure names, exactly as the original request asked. This is a one-line
change on the `portfolio-browser` side (its `_PROJECTION_RETURNS` config-to-wire-value mapping)
whenever that feature is wired to a live service — not a redesign of anything already built
there, since that repo currently only talks to a fake client it fully controls.

**Validation**: A new `app/services/projection_returns.py` module, mirroring
`performance_attributes.py`'s shape but *without* its `NoAttributesRequestedError` check — an
empty `return` list is valid here (FR-012), unlike the performance endpoint, which requires at
least one measure.

```python
SUPPORTED_PROJECTION_RETURNS: frozenset[str] = frozenset({"ITD (Ann.)", "1Y", "3Y", "5Y"})

def validate_returns(returns: list[str]) -> None:
    invalid = [r for r in returns if r not in SUPPORTED_PROJECTION_RETURNS]
    if invalid:
        raise UnsupportedAttributeError(requested=invalid, supported=sorted(SUPPORTED_PROJECTION_RETURNS))
```

`UnsupportedAttributeError` and its existing 422 handler are reused unmodified.

## 3. Start-date defaulting: reuse `AccountsService`, but NOT `TimeseriesDateResolver`

**Decision**: `AccountsService.get_summary()` is reused unmodified to look up
`position_ladder.from_date`/`to_date`. `TimeseriesDateResolver` is **not** reused — a new, small
piece of date-resolution logic is added directly in `ProjectionService`, following the same
*pattern* (business-day forward-adjustment, capped) but with the cap and the default pointed in
the opposite direction.

**Correction to the implementation hint**: The original request said to reuse
`TimeseriesDateResolver` for the start-date default. Reading it (`app/services/
timeseries_date_resolver.py`) shows why that can't be literal: its whole purpose is defaulting an
*omitted* start to a required source's **earliest** recorded date (`start = raw_start if raw_start
is not None else max(required_source_earliest_dates)`), and its `_adjust_forward_capped_at_today`
caps every date at **today**, raising `FutureEndDateError` for anything later. This endpoint needs
exactly the opposite on both counts: an omitted `start` defaults to the account's **most recently**
recorded date, and `projection_date` is expected — indeed required — to be in the future; capping
it at today would break the endpoint's entire purpose. Forcing reuse of `TimeseriesDateResolver`
here would mean bending its documented contract until it no longer means what its own name and
tests say it means, which is a worse outcome than the small amount of new code below (SOLID's
single-responsibility gate — Constitution Principle II — is exactly the reason not to overload it).

The new logic (a private method on `ProjectionService`, not a new public service, since nothing
else in this codebase needs "adjust forward, capped at an arbitrary date" — if a second caller
ever needs it, extracting it then is a mechanical refactor, not a redesign):

```python
def _resolve_start(self, raw_start: date | None, ladder_range: AccountResourceRange) -> date:
    start = raw_start if raw_start is not None else ladder_range.to_date
    adjusted: date = pd.bdate_range(start=start, periods=1)[0].date()
    if adjusted > ladder_range.to_date:
        adjusted = pd.bdate_range(end=ladder_range.to_date, periods=1)[0].date()
    if adjusted < ladder_range.from_date:
        raise MissingRequiredSourceError(...)  # reused unmodified — same 422 as every other endpoint
    return adjusted
```

`projection_date` gets no such cap — a future date is the entire point — but it is still required
to be strictly later than the resolved `start`, checked directly (see #6).

## 4. Historical series: reuse `TimeSeriesService`'s own account-level `market_value` aggregation

**Decision**: The historical series is built with the exact pattern
`app/services/timeseries_service.py::TimeSeriesService.get_series` already uses for its own
`market_value` attribute: `ladder_df.groupby("date", as_index=False)["market_value"].sum()` then
`expand_business_days(aggregated, ["market_value"], from_date, resolved_start)`, then
`aggregate_last_observation(..., periodicity, from_date)`.

**Rationale**: This is the *only* place in the existing codebase that already computes an
account-level (summed-across-positions) `market_value` series — reusing it exactly means no new
aggregation logic, and guarantees this endpoint's `"Historical"` series is numerically identical
to what `/v1/accounts/{account}/timeseries?attribute=market_value` already returns for the same
range, which is a testable, checkable invariant.

## 5. Projection math: de-annualize via the 260th root, computed from the existing performance measures

**Correction (2026-09-24)**: The original pinned contract specified `daily_rate =
annualized_return * sqrt(260)`, and that formula was implemented as originally specified. It is
**wrong** and has been fixed. `sqrt(260)` is a volatility-scaling factor (used to annualize a
*standard deviation*, e.g. daily-vol → annual-vol); it has no valid role in converting an
annualized *return* down to a single business day's rate. Using it produced grossly incorrect
projections — a real, reproduced example: an account with a 24.2% annualized 3Y return
(`0.24206118393219178`) produced a "daily rate" of `0.242 * sqrt(260) ≈ 3.90` — i.e. a **390%**
single-day return, turning a $33,190 market value into $162,738 the very next business day. The
correct de-annualization is the **260th root**, the exact inverse of how
`performance_metrics.py` itself annualizes a return one line away
(`itd_ann = (1 + itd) ** (260 / elapsed) - 1`):

**Decision**: For each requested-and-computable return, its annualized rate as of the resolved
`start` date is read from `app/services/performance_metrics.py::compute_performance_measures()`
(reused unmodified, via `daily_portfolio_return.compute_daily_portfolio_return()`, exactly as
`PerformanceService` already does) — specifically, the row where `date == resolved_start`. A
measure with `NaN` at that row (not enough preceding history — the same "insufficient history"
signal `PerformanceService` already relies on) means that return is silently skipped (FR-011).

For each survivor:

```python
daily_rate = (1 + annualized_return) ** (1 / 260) - 1
business_days = pd.bdate_range(start=resolved_start, end=projection_date)
values = [start_market_value * (1 + daily_rate) ** t for t in range(len(business_days))]
```

Worked example: a 24.2% annualized 3Y return de-annualizes to
`(1.24206118393219178) ** (1/260) - 1 ≈ 0.000834` (~0.08% per business day) — a $33,190 market
value compounds to ≈ $33,217.68 the next business day, not $162,738.

`start_market_value` is the historical series' own value on `resolved_start` (#4) — so the
projected series and the historical series provably share their starting point (FR-011's visual
requirement, satisfiable because the underlying data literally is the same number).

**Rationale**: The 260th root is the mathematically correct inverse of this codebase's own
annualization convention (260-trading-day year, confirmed in `performance_metrics.py` and this
service's own `CLAUDE.md`), produces sane, compoundable daily rates, and is what "a transparent,
illustrative forward compounding of the account's own historical rate" (the pinned contract's own
stated intent) actually requires — the original `sqrt(260)` formula never delivered that intent,
it was simply wrong.

## 6. Periodicity bucketing: reuse `aggregate_last_observation()`, once per series

**Decision**: Each daily series (the historical one, and each projected one) is wrapped into a
small two-column DataFrame (`date`, `market_value`) and passed through
`app/services/periodicity_aggregation.py::aggregate_last_observation()` **unmodified**,
independently — exactly the same per-series call pattern
`PositionTimeSeriesService.get_series` already uses per position, with "series label" standing in
for "position name." The historical leg's aggregation call uses the ladder's own `from_date` as
its window-clamp `resolved_start` argument; each projected leg's call uses the endpoint's
resolved `start` instead — each series is clamped to *its own* range's beginning, which is what
makes the two legs' window boundaries land on identical calendar-aligned dates when concatenated
(both are computed from the same real calendar, just with different valid ranges).

**Rationale**: No new aggregation logic; identical validated correctness to every other
periodicity-aware endpoint in this service.

## 7. Error handling: RFC 7807, matching this service's actual status-code conventions exactly

**Decision**:

| Condition | Exception (new unless noted) | Status |
|---|---|---|
| Account has no capital ledger or position ladder at all | `AccountNotFoundError` (existing) | 404 |
| Account known but has no ingested position ladder | `PositionLadderNotIngestedError` (existing) | 422 |
| `resolved_start` precedes the ladder's own earliest recorded date | `MissingRequiredSourceError` (existing) | 422 |
| `projection_date` not strictly later than resolved `start` | **`InvalidProjectionRangeError`** (new) | 422 |
| Unsupported `periodicity` value | `UnsupportedPeriodicityError` (existing) | 422 |
| Unsupported `return` value | `UnsupportedAttributeError` (existing) | 422 |

**Correction to the pinned contract**: the browser-side `contracts/portfolio-analysis-api.md`
loosely listed "404: Account/resource not found" for *both* "no position ladder ingested" and "no
history at all." Reading this service's own `main.py` shows those are two genuinely different
cases with two different existing status codes: total absence of any resource is 404
(`AccountNotFoundError`, reused as-is by every other endpoint), while a *known* account missing
specifically a position ladder is 422 (`PositionLadderNotIngestedError`, likewise reused as-is by
`position_timeseries_service.py` and `position_timeseries.py`'s own router). This spec follows
this service's own real, already-shipped convention rather than the browser side's necessarily
approximate guess — the browser's spec.md and contract only ever required "a clear, structured
error" (SC-005), never a specific code, so this is not a contract break.

`InvalidProjectionRangeError` mirrors `InvalidDateRangeError`'s exact shape:

```python
class InvalidProjectionRangeError(Exception):
    def __init__(self, start: date, projection_date: date, message: str | None = None) -> None:
        self.start = start
        self.projection_date = projection_date
        self.message = message or (
            f"Projection date {projection_date} is not later than the resolved start "
            f"date {start}. A projection must run forward in time."
        )
        super().__init__(self.message)
```

Registered in `main.py` with a 422 handler, following the exact pattern every other domain
exception already uses (`_problem(request, 422, "invalid-projection-range", "Invalid Projection Range", exc.message)`).

## 8. Layering: a new `ProjectionService`, following `PerformanceService`'s/`PositionTimeSeriesService`'s pattern exactly

**Decision**: `app/services/projection_service.py::ProjectionService`, constructor-injected with
`ladder_repo: LadderRepository`, `accounts_service: AccountsService` — no `capital_repo` (like
`PerformanceService`, every measure this endpoint needs comes from the position ladder alone) and
no `date_resolver` (per #3, that logic is now local to this service). One public method,
`get_projection(...)`, orchestrating validation → date resolution → historical build → per-return
projected build → response assembly, in that order — the same structure every existing
`*Service.get_series`/`get_performance` method already follows.

**Rationale**: Matches Constitution Principle II (data access / calculation / transport kept in
separate layers) and mirrors an existing, reviewed pattern rather than inventing a new one, per
the original request's own explicit instruction.
