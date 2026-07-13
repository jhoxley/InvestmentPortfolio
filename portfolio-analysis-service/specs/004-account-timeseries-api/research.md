# Phase 0 Research: Account Time Series API

All unknowns were resolvable from the existing codebase (features 001–003) and the clarified
spec. No external technology research was required — this feature adds three new read-only
endpoints to the existing FastAPI service using its existing stack.

## 1. Reusing `expand_business_days()` for the join, not just ingestion

**Decision**: Both the capital-ledger-derived attributes and the aggregated `market_value`
series are individually passed through the existing `app/services/business_day_expansion.py`
`expand_business_days()` helper (built in feature 003) before being joined, rather than writing
new forward-fill logic for this endpoint.

**Rationale**: The helper already does exactly what FR-011 requires — calendar reindex,
forward-fill, then filter to business days, over an arbitrary `[start, end]` range. The capital
ledger and the position-ladder-derived market-value series are two independent single-column
(well, three-column for capital) date series once aggregated; feeding each through the same
helper guarantees identical, already-tested forward-fill semantics on both sides of the join,
and directly extends this helper's proven value beyond its original extraction purpose.

**Alternatives considered**: Write bespoke reindex/ffill logic scoped to this endpoint —
rejected as pure duplication of already-correct, already-tested code for no benefit.

## 2. Where the position-ladder aggregation happens

**Decision**: `market_value` is aggregated (summed by date across all sub-accounts, including
Cash) from the stored `ladder.xlsx` *before* being passed to `expand_business_days()`, not
after.

**Rationale**: The stored ladder already has one row per (business day, active sub-account)
with no internal gaps (guaranteed by `LadderExpander` at ingestion time). Grouping by date and
summing `market_value` first collapses this to one row per business day covering
`[ladder.from_date, ladder.to_date]`; running that aggregate through `expand_business_days()`
then only needs to forward-fill the *trailing* gap between the ladder's own `to_date` and the
resolved end date (per FR-011) — exactly the same shape of problem the capital ledger side
faces, so both sides use the identical mechanism.

**Alternatives considered**: Reindex/ffill each sub-account individually before summing —
rejected as unnecessary; the ladder is already gap-free per sub-account by construction, so
per-sub-account forward-fill would be redundant work producing an identical aggregate.

## 3. Date resolution (defaulting + business-day adjustment) as its own module

**Decision**: A new, small `app/services/timeseries_date_resolver.py` implements FR-006 through
FR-010 using `pandas.bdate_range`, not manual weekday arithmetic:
- "next business day on/after `d`" = `pd.bdate_range(start=d, periods=1)[0].date()`
- "most recent business day on/before `today`" = `pd.bdate_range(end=today, periods=1)[0].date()`
- "the business day before `today`" (T-1, default end) = `pd.bdate_range(end=today, periods=2)[0].date()`

**Rationale**: These three primitives compose directly into every date rule the spec defines
(FR-007's default end, FR-008's forward-adjustment-capped-at-today). Using `pandas.bdate_range`
matches the exact mechanism `LadderExpander` and `CapitalLedgerValidator` already use for
business-day arithmetic elsewhere in this codebase, rather than introducing a second,
hand-rolled weekday-math implementation that could subtly disagree with the existing one.

**Alternatives considered**: Manual `date.weekday()` branching — rejected; `pandas.bdate_range`
is already the established, tested primitive for this exact class of problem in this codebase.

## 4. Extracting shared account-name validation and repository DI providers

**Decision**: Extract `_ACCOUNT_NAME_PATTERN` / `_validate_account_name()` into
`app/validators/account_name.py`, and the `LadderRepository`/`CapitalRepository` FastAPI
provider functions into `app/api/dependencies.py`. `ladder.py` and `capital.py` are refactored
to import from these shared modules instead of keeping their own local copies.

**Rationale**: Feature 003 deliberately kept a second copy of the account-name regex in
`capital.py` rather than extracting it, reasoning that two copies of ~10 lines wasn't worth a
new shared module. This feature needs a *third* copy (in the new `timeseries.py` router) and
also needs *both* repositories together for the first time (the existing `ladder.py`/`capital.py`
each only ever needed their own one repository) — crossing the "rule of three" threshold that
justified deferring extraction last time. Extracting now is a small, mechanical,
behaviour-preserving refactor of existing code, not a redesign.

**Alternatives considered**: Add a third local copy in `timeseries.py` — rejected; three
near-identical copies of the same validation/wiring logic is the point at which the earlier
"not worth it yet" judgement flips.

## 5. Response shape for dynamic per-request attribute sets

**Decision**: `TimeSeriesEntry` is a Pydantic model with `date: date` as its only declared
field and `model_config = ConfigDict(extra="allow")`, populated with only the requested
attribute keys per entry (e.g., `TimeSeriesEntry(date=d, capital=1000.0)` when only `capital`
was requested).

**Rationale**: FR-015 explicitly prohibits returning null/missing values for attributes that
weren't requested or couldn't be computed — the response shape must vary per request rather
than always exposing all five attribute fields as `Optional`. Pydantic v2's `extra="allow"`
directly supports this while still giving FastAPI/OpenAPI a documented `date` field and a
documented (if loosely typed) `additionalProperties` shape for the dynamic attribute values.

**Alternatives considered**: A fixed model with all five attributes as `float | None` —
rejected; this would make "not requested" and "requested but N/A" indistinguishable in the
JSON, directly contradicting FR-015's "MUST NOT return... null values" language.

## 6. Reusing existing exceptions vs. adding new ones

**Decision**: Reuse `AccountNotFoundError` (404, FR-002) with a feature-specific message
override. Add four new exception types: `NoAttributesRequestedError`,
`UnsupportedAttributeError`, `FutureEndDateError`, `InvalidDateRangeError`, and
`MissingRequiredSourceError` — all 422, each with its own RFC 7807 `type` slug and handler in
`main.py`, following the established one-exception-per-distinct-validation-rule pattern from
features 001–003.

**Rationale**: `AccountNotFoundError`'s handler is already generic (keys on exception type, not
message content) and the constructor already accepts a message override — reused exactly as it
was for the capital ledger's 404 case in feature 003. The five new validation rules (FR-003,
FR-004, FR-009, FR-010, FR-015) are each semantically distinct failure modes with different
required error context (e.g. `MissingRequiredSourceError` needs to name the specific attribute
and source; `FutureEndDateError` needs the supplied end date and today's date) — matching this
codebase's existing convention of one exception class per distinct rule rather than one
catch-all with a mode flag.

**Alternatives considered**: A single generic `ValidationError(message)` for all five new rules
— rejected; loses the structured per-field context the existing `SchemaValidationError`,
`EmptyCapitalDateRangeError`, etc. patterns rely on, and would make it harder to test each rule
independently.

## 7. Concrete endpoint paths

**Decision**:
- `GET /v1/accounts/{account_name}/timeseries` — main endpoint (US1)
- `GET /v1/timeseries/attributes` — metadata endpoint (US2)
- `GET /v1/accounts` — accounts-enumeration endpoint (US3)

**Rationale**: The main endpoint mirrors the already-established `/v1/accounts/{account_name}/
{ladder|capital}` item-detail pattern. The metadata endpoint is a property of the timeseries
*capability* itself (not account-scoped), so it lives under a new `/v1/timeseries` collection
prefix as a sibling to the account-scoped resource. `/v1/accounts` (no path segment) is the
"list" verb the existing `/v1/accounts/{account_name}/...` family has never had — a natural,
minimal addition rather than a new resource family.

**Alternatives considered**: Nesting metadata under `/v1/accounts/{account_name}/timeseries/
metadata` — rejected; the attribute list is identical for every account (it describes the
*capability*, not a specific account's data), so scoping it under an account name would be
misleading and would require picking an arbitrary account to satisfy the path.
