# Research: Position & Portfolio-Weighted Daily Returns

No `NEEDS CLARIFICATION` markers remain in the Technical Context — this feature reuses the
existing stack, storage mechanism, and testing tools end to end. This document records the
design decisions made while grounding the plan in the current codebase (`app/services/`,
`app/repositories/ladder_repository.py`, `app/services/position_attributes.py`).

## 1. Where the new computation is chained into ingestion

**Decision**: Add a new `ReturnsEnrichmentService` with an `enrich(priced_df) -> pd.DataFrame`
method, invoked in `IngestionService.ingest()` immediately after the existing
`self._enrichment_service.enrich(...)` (`PricingEnrichmentService`) call, on both the
new-ladder path and the checksum-unchanged refresh path.

**Rationale**: `position_return` and `weighted_position_return` are pure functions of columns
that only exist *after* pricing enrichment (`price`, `portfolio_weight`) plus columns already
present on the base ladder (`total_income`, `quantity`). Chaining as a second stage keeps
`PricingEnrichmentService` untouched (Open/Closed) and mirrors the existing pipeline shape
documented in `IngestionService`'s docstring (`validate → expand → enrich → persist`), which
this feature extends to `validate → expand → price-enrich → return-enrich → persist`. Because
`IngestionService` already re-runs the *entire* enrichment chain on a checksum-unchanged
refresh (feature 002's FR-013), the new stage automatically inherits that same "always
recomputed from current inputs" behaviour for free — no special-casing needed for FR-006.

**Alternatives considered**:
- *Compute inside `PricingEnrichmentService.enrich()`*: rejected — conflates two responsibilities
  (fetching/pricing vs. deriving returns) in one class, violating Single Responsibility, and
  would force every `PricingEnrichmentService` unit test to also carry return-specific fixtures.
- *Compute lazily at read time (in `PositionTimeSeriesService`)*: rejected — contradicts FR-007
  ("persist ... so retrieving them later does not require recomputation") and User Story 3's
  explicit requirement that repeated reads do no extra work; would also require every reader of
  `ladder.xlsx` (not just the timeseries endpoint) to duplicate the calculation.

## 2. Computation strategy: vectorized pandas, not row-by-row

**Decision**: Compute both columns with `groupby("sub_account")` + `shift(1)` for the T-1 lookups
(`price`, `total_income`, `portfolio_weight`), matching the vectorized style already used in
`PricingEnrichmentService.enrich()` (e.g. `groupby("date")["market_value"].transform("sum")`).

```text
sorted by (sub_account, date)
prev_price     = group["price"].shift(1)
prev_income    = group["total_income"].shift(1)
prev_weight    = group["portfolio_weight"].shift(1)

income_per_share = where(quantity == 0, 0, (total_income - prev_income) / quantity)
position_return   = where(prev_price.isna(), 0, (price - prev_price + income_per_share) / prev_price)
weighted_position_return = position_return * prev_weight.fillna(0)
```

**Rationale**: The ladder is already sorted/grouped by `sub_account` elsewhere in the codebase
(`LadderExpander`, `PricingEnrichmentService` both `groupby("sub_account", ...)`); `shift(1)`
within a sorted group is the standard pandas idiom for "previous row in this group" and avoids
an O(n²) row-by-row Python loop over what can be several years of daily rows per sub-account.
`shift(1)` naturally produces `NaN` for each group's first row, which conveniently *is* the
first-trade-date condition (FR-004) — detecting it is `prev_price.isna()`, not a separate
explicit "is this the first row" flag.

**Alternatives considered**:
- *Python-level loop with explicit prior-row tracking*: rejected — unnecessary for a
  pure per-group sequential dependency that pandas already expresses natively; slower and more
  error-prone than the vectorized form.
- *`pd.DataFrame.diff()` for the price/income deltas*: considered but rejected in favour of
  explicit `shift(1)` + subtraction, because `income_per_share` needs the *current* row's
  `quantity` as the divisor (not a diffed value), and keeping `prev_price`/`prev_income`/
  `prev_weight` as named intermediate columns makes the zero-guard `where(...)` clauses and unit
  tests easier to reason about than chained `.diff()` calls.

**Implementation-time refinement (found during `/speckit-implement`)**: plain `shift(1)` alone
only detects a sub-account's true *first-ever* row (`shift(1)` → `NaN`) — it does **not** detect
a *gap* between two non-adjacent rows for the same sub-account (`shift(1)` still returns
whatever row happens to be previous in sort order, regardless of the calendar distance between
them). This under-implements spec.md's Edge Cases ("a sub-account has a gap in its ladder
history ... re-entry date is treated the same as any other first appearance") and SC-002
("including a sub-account that re-enters the ladder after a gap"). The implemented service adds
a cheap, precise adjacency check alongside `shift(1)`: `gap_days = (date - date.shift(1)).dt.days`,
and a row only has a valid T-1 when `gap_days <= 3` (the maximum real gap between two adjacent
LadderExpander-produced business-day rows for an active position — Friday to Monday — since
`pd.bdate_range` observes no holiday calendar, per this repository's root `CLAUDE.md`). This
`has_prior_row` flag now gates *both* `position_return`'s and `weighted_position_return`'s
zero-default, not just the bare `shift(1)` `NaN` check originally described above. See
`app/services/returns_enrichment_service.py` for the final implementation.

## 3. Division-by-zero handling

**Decision**: Reuse the existing `Series.mask(...)`/`Series.where(...)` safe-division pattern
already established in `PricingEnrichmentService.enrich()` for `portfolio_weight`
(`totals.mask(totals == 0, other=1.0)` then `.where(totals != 0, other=0.0)`), applied here to
guard `quantity == 0` (FR-005) and the first-row `NaN` previous-price/weight case (FR-004).

**Rationale**: Consistency with an already-reviewed, already-tested pattern in the same
pipeline; avoids introducing exceptions or `try/except ZeroDivisionError` for a case the spec
defines as expected/normal (a fully divested position, or a sub-account's first ladder row),
not exceptional.

**Alternatives considered**: Raising a new exception type for zero-quantity/zero-price rows —
rejected; the spec's Edge Cases section explicitly calls for fail-soft-to-0 behaviour, not
ingestion failure, since these are routine states (full divestment, first purchase) rather than
data-integrity problems.

## 4. Exposing the new metrics through the position time series API

**Decision**: Add two entries to `app/services/position_attributes.py`'s `ATTRIBUTE_DEFINITIONS`
list (with `source="position_ladder"`, matching every existing entry) and two matching entries
to `COLUMN_FOR_ATTRIBUTE` (`"position_return": "position_return"`,
`"weighted_position_return": "weighted_position_return"`). No changes are needed to
`PositionTimeSeriesService`, `app/api/position_timeseries.py`, or
`app/models/position_timeseries.py` — all three are already fully generic over
`SUPPORTED_ATTRIBUTES`/`COLUMN_FOR_ATTRIBUTE`/`ATTRIBUTE_DEFINITIONS` (confirmed by reading
`position_timeseries_service.py`, which builds `value_columns` and each response entry purely
from those two lookup tables, with `pnl` as the only special-cased attribute since it's derived
at read time rather than stored).

**Rationale**: This is the single source of truth the existing code already uses for both
FR-008 (request validation) and FR-009 (metadata endpoint) — exactly the pattern the module's
own docstring describes ("Both FR-008 ... and FR-017 ... read from the same
`ATTRIBUTE_DEFINITIONS` list, so the two can never drift apart"). Adding entries there is the
minimal, idiomatic change; no other production code needs to know these two attributes exist.

**Alternatives considered**: A dedicated `/positions/returns` endpoint — rejected; the
clarification already resolved in spec.md explicitly chose "extend the existing `attribute`
enum," not a new resource, and a new endpoint would duplicate date-range resolution, position
filtering, and business-day expansion logic that `PositionTimeSeriesService` already provides
generically.

## 5. Interaction with the checksum-unchanged refresh path and `LadderRepository`

**Finding (no code change required)**: `LadderRepository.read_ladder_df()` (used only on the
refresh path) already hard-codes its returned column list to
`["date", "sub_account", "book_cost", "quantity", "total_income"]` — the base, pre-enrichment
columns — explicitly dropping whatever enrichment columns exist in the currently-stored file.
Since `position_return`/`weighted_position_return` are enrichment-derived (like
`price`/`market_value`/`portfolio_weight`), they are already excluded by this existing allowlist
with zero changes needed. `LadderRepository.read_full_df()` (used by the position time series
endpoint) reads every stored column generically via `pd.read_excel`, so the two new columns
appear there automatically once `IngestionService` starts writing them — no repository change
needed on that path either.

**Rationale for recording this as a research finding rather than skipping it**: it resolves what
would otherwise look like a gap (the refresh path visibly drops price/weight columns — would it
also need to explicitly drop the two new return columns?) by confirming the existing allowlist
approach already generalizes correctly to any future enrichment column, including these two.

## 5b. Business-day fixture dates (found during `/speckit-implement`, BDD steps)

spec.md's illustrative User Story 2 acceptance scenario uses 2024-03-03/2024-03-04 as
consecutive "ladder dates" — but 2024-03-03 is a **Sunday**. `expand_business_days` correctly
excludes non-business-days, so a raw ledger row dated on a Sunday can never survive into a real
position ladder. This is purely a documentation-illustration artifact (spec.md's prose is about
the *formula*, not about validating specific calendar dates) and required no spec.md change —
the BDD fixture in `tests/steps/ladder_returns_steps.py` uses the nearest equivalent pair of
real consecutive business days (2024-03-04 Monday / 2024-03-05 Tuesday) instead.

## 5c. Cross-feature performance impact (found during `/speckit-implement`, Polish phase)

Widening every stored ladder by 2 columns (`position_return`, `weighted_position_return`, on
top of feature 002's `price`/`market_value`/`portfolio_weight`) measurably slowed full-ladder
reads via `LadderRepository.read_full_df()`, pushing feature 005's existing performance test
(`TestPositionTimeseriesSC001MultiPositionPerformance`, 50 positions over 5 years) from
comfortably under its original 10s budget to ~12-13s.

**Investigated and rejected**: passing `usecols=` to `pd.read_excel(..., engine="openpyxl")` so
only the columns a given request actually needs are parsed. Profiling (`cProfile`) showed this
has no effect — `openpyxl`'s reader (`openpyxl/worksheet/_reader.py:parse_cell`) parses every
cell in the sheet via XML traversal *before* pandas applies `usecols` filtering, so read time is
dominated by total sheet width regardless of how many columns the caller actually wants. This
was reverted (no code changes to `LadderRepository`/`PositionTimeSeriesService` beyond this
feature's original scope).

**Decision**: raise `TestPositionTimeseriesSC001MultiPositionPerformance`'s threshold from 10s
to 15s (user-approved), documenting the cause inline in `tests/unit/test_performance.py`, rather
than pursuing a more invasive fix (switching XLSX engines, e.g. to `python-calamine`, was
identified as the actual root-cause fix but rejected as a new dependency + cross-cutting
architecture change disproportionate to this feature's scope — a candidate for a future,
dedicated feature if ladder width continues to grow).

## 6. Test structure

**Decision**: Follow the existing per-service unit test + BDD feature/steps split:
- `tests/unit/test_returns_enrichment_service.py` — pure computation tests against small
  hand-built DataFrames (first-date zero rule, zero-quantity guard, T-1 weight vs. same-date
  weight, multi-sub-account scenarios), mirroring `tests/unit/test_pricing_enrichment_service.py`.
- A new `tests/features/ladder_returns.feature` (+ `tests/steps/ladder_returns_steps.py`) for
  User Stories 1–3 (ingestion-time computation and persistence stability across repeated reads).
- User Story 4 (API exposure) scenarios are added as new `@us4`-marked scenarios in the existing
  `tests/features/retrieve_position_timeseries.feature` / `retrieve_position_timeseries_steps.py`
  (feature 005's file), since they exercise the same endpoint and step vocabulary
  (`position=...&attribute=...` requests) that file already defines — a new feature file would
  duplicate that step vocabulary rather than reuse it. Final placement is confirmed in
  `tasks.md`.

**Rationale**: Matches `pyproject.toml`'s existing `us1`–`us4` pytest markers convention and the
one-service-one-test-file pattern already used for `PricingEnrichmentService`.
