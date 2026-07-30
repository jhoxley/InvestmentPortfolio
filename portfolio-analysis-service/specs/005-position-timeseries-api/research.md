# Phase 0 Research: Position Time Series API

All unknowns were resolvable from the existing codebase (features 001–004) and the clarified
spec. No external technology research was required — this feature adds three new read-only
endpoints to the existing FastAPI service using its existing stack, reusing every shared
service and helper that feature 004 already extracted.

## 1. `read_full_df()` already gives everything this endpoint needs — no repository changes

**Decision**: `LadderRepository.read_full_df(account_name)` (added in feature 002, already used
by feature 004's account-level `market_value`) is reused unchanged. It returns every stored
column — `date`, `sub_account`, `book_cost`, `quantity`, `total_income`, `price`,
`market_value`, `portfolio_weight` — which covers all six of this endpoint's attributes
directly (`market_value`→`market_value`, `book_cost`→`book_cost`, `income`→`total_income`,
`close_price`→`price`, `quantity`→`quantity`, `pnl`→computed from the other three).

**Rationale**: Unlike feature 004 (which had to aggregate `market_value` *across*
sub-accounts, collapsing the `sub_account` dimension), this feature needs to *keep*
`sub_account` as the grouping key. `read_full_df()` already returns the ungrouped,
per-sub-account rows — no new repository method is needed, and none of `read_full_df()`'s
existing five callers (the refresh path via `read_ladder_df`, feature 004) are affected.

**Alternatives considered**: Add a new `read_positions_df()` repository method — rejected;
it would be byte-for-byte identical to the existing `read_full_df()`, pure duplication for no
behavioural difference.

## 2. Distinguishing "still held, ladder just stale" from "genuinely divested" per position

**Decision**: For each position in the effective set, compare its own last recorded row's
date against the account's position-ladder `to_date` (from `AccountMeta`/`AccountSummary`,
already exposed by the existing `AccountsService.get_summary()`):
- `last_row_date == ladder.to_date` → **still held**: forward-fill its last known values
  through the resolved end date, via the same `expand_business_days()` call already used by
  feature 004, by passing `end=resolved_end`.
- `last_row_date < ladder.to_date` → **genuinely divested**: cap the expansion's `end`
  parameter at that position's own `last_row_date` instead of `resolved_end`, so
  `expand_business_days()` never forward-fills past the real point of divestment.

Symmetrically, each position's expansion `start` is `max(resolved_start, position_first_date)`
— never earlier than the position's own first recorded row — so no entries are fabricated
before a position existed.

**Rationale**: `LadderExpander` (feature 001) already guarantees that a still-held equity
sub-account's rows extend through the *entire* stored ladder's date range (one row per
business day while `quantity > 0`), and a Cash-like/divested sub-account's rows simply stop
existing once no longer applicable. This means "does this position's last row land exactly on
the ladder's own `to_date`" is already a reliable, pre-existing signal for "still held as of
the last refresh" — no new metadata or ingestion-side change is needed to support this
distinction; it falls directly out of data already being written by feature 001/002. This
mirrors the account-level endpoint's own forward-fill-for-staleness behaviour (FR-011 in
004-account-timeseries-api), just decided per position instead of once for the whole account.

**Alternatives considered**: Never forward-fill past a position's last recorded row (the
spec's original FR-013 draft) — rejected after implementation research surfaced that this
would make a currently-held position's chart line visibly lag behind "today" by however stale
the last ladder ingestion was, contradicting the "behaves the same way as the existing
timeseries endpoint" instruction for date handling. Resolved via a follow-up clarification
(see spec.md Clarifications) before finalizing this plan.

## 3. Reusing `expand_business_days()` and `TimeseriesDateResolver` per position, unchanged

**Decision**: The same `expand_business_days()` helper (business_day_expansion.py) and
`TimeseriesDateResolver` (unchanged) used by the account-level endpoint are called once per
position in the effective set — `TimeseriesDateResolver.resolve()` once for the whole request
(using `[ladder.from_date]` as the sole required-source-earliest-date), then
`expand_business_days()` once per position with that position's own computed `[start, end]`
sub-range (per research §2).

**Rationale**: Both helpers already do exactly what's needed with zero modification —
`TimeseriesDateResolver` doesn't care how many required sources there are (it already accepts
a list and takes the max), and `expand_business_days()` is already parameterised per-call by
`[start, end]`, so calling it once per position with a position-specific range is exactly its
existing contract, not a new capability.

**Alternatives considered**: Reindex/ffill all positions in a single wide DataFrame (one
column per position per attribute) — rejected; it would require inventing new fill-then-trim
logic to handle each position's differing active window, duplicating what
`expand_business_days()` already does correctly per-series, for no performance benefit at this
service's scale (SC-001: 50 positions × 5 years).

## 4. New service layer: `PositionsService` and `PositionTimeSeriesService`

**Decision**: Two new services, following the same separation `AccountsService`/
`TimeSeriesService` already established in feature 004:
- `PositionsService` (`app/services/positions_service.py`): given a `sub_account`-indexed
  DataFrame (from `read_full_df()`), computes the distinct position list with per-position
  first/last recorded dates (FR-016) and resolves the effective position set from a requested
  list (FR-004/FR-005 intersection, silently dropping mismatches).
- `PositionTimeSeriesService` (`app/services/position_timeseries_service.py`): orchestrates
  attribute validation, account validation (delegating to the existing `AccountsService`),
  date resolution (delegating to the existing `TimeseriesDateResolver`), effective-position-set
  resolution (delegating to the new `PositionsService`), per-position expansion (research §2),
  and `pnl` computation, then assembles the flat response (FR-014).

**Rationale**: `PositionsService` is reused by both the main endpoint (to compute the
effective set) and the standalone `/positions` helper endpoint (to enumerate all positions),
avoiding duplicating the groupby/first-last-date logic in two places — the same reuse
rationale that produced `AccountsService` in feature 004. `PositionTimeSeriesService` mirrors
`TimeSeriesService`'s role exactly, keeping single-responsibility boundaries: `PositionsService`
never touches attributes/dates: `PositionTimeSeriesService` never touches ladder file I/O
directly (it goes through `LadderRepository` and `PositionsService`).

**Alternatives considered**: Fold position enumeration directly into
`PositionTimeSeriesService` and have the `/positions` endpoint call it with a null attribute
list — rejected; would force the main endpoint's service to expose a mode not part of its own
single responsibility (building a time series), and would need to accept unused parameters
just to satisfy the enumeration endpoint's simpler contract.

## 5. Attribute definitions as a second, endpoint-scoped source of truth

**Decision**: A new `app/services/position_attributes.py`, structurally identical to
`app/services/timeseries_attributes.py` (an `ATTRIBUTE_DEFINITIONS` list, a
`SUPPORTED_ATTRIBUTES` frozenset, and `validate_attributes()`), but with this endpoint's own
six-name set (`market_value`, `income`, `book_cost`, `pnl`, `close_price`, `quantity` — no
`capital`) and no `requires_capital_ledger`/`requires_position_ladder` split (every attribute
here requires only the position ladder, so that distinction doesn't apply).

**Rationale**: FR-008/SC-005 require this endpoint's accepted attribute set to be both
distinct from and always in sync with its own metadata endpoint — the same single-source-of-
truth pattern `timeseries_attributes.py` already uses for the account-level endpoint's FR-004/
FR-017 pairing (SC-004 there). A second module (not a parameterised generalisation of the
first) keeps each endpoint's attribute set independently testable and avoids threading a
"which endpoint" flag through shared validation code for two lists that only coincidentally
overlap on four names.

**Alternatives considered**: Generalise `timeseries_attributes.py` to accept an "endpoint"
parameter and branch internally — rejected; the two attribute sets differ in both membership
and required-source shape (this endpoint has no multi-source attributes), so a shared module
would need conditional branches for behaviour that is otherwise simple, static data.

## 6. Reusing existing exceptions; one new exception for the single-required-source case

**Decision**: Reuse, unmodified: `AccountNotFoundError` (404 — no resource of any kind
ingested), `NoAttributesRequestedError` (422), `UnsupportedAttributeError` (422, this
endpoint's own supported-set message), `FutureEndDateError` (422), `InvalidDateRangeError`
(422), and `MissingRequiredSourceError` (422 — reused for the "`start` before the ladder's own
earliest date" case, FR-010, with `source="position_ladder"` and `attribute` set to the
comma-joined requested attribute list, since the failure isn't specific to one attribute here).
Add one new exception, `PositionLadderNotIngestedError` (422, FR-002/FR-016), for "account is
known to `/v1/accounts` but has no ingested position ladder at all."

**Rationale**: `PositionLadderNotIngestedError` is genuinely a new failure mode this codebase
hasn't needed before: every prior 422 tied to a *specific* attribute or date value via
`MissingRequiredSourceError`, but this endpoint's very first validation step (FR-002) is
account-wide and attribute-independent — reusing `MissingRequiredSourceError` here would force
an artificial "which attribute" value into an error that isn't really about any one attribute.
Everything else maps directly onto existing, already-tested exception classes with no
behavioural change needed.

**Alternatives considered**: Reuse `AccountNotFoundError` with a 422 override for this case —
rejected; its existing handler is hard-wired to 404 (matching FR-002's precedent for "entirely
unknown account"), and giving one exception class two different status codes depending on
call site would break the established one-exception-one-status-code convention this codebase
follows throughout `main.py`.

## 7. Concrete endpoint paths and OpenAPI grouping

**Decision**:
- `GET /v1/accounts/{account_name}/position` — main endpoint (US1), singular per the user's
  literal request.
- `GET /v1/accounts/{account_name}/positions` — enumeration helper endpoint (US2), plural.
- `GET /v1/positions/attributes` — metadata endpoint (US3), mirroring `/v1/timeseries/
  attributes`'s "describes the capability, not a specific account" placement.
- All three tagged `Position Timeseries` in the OpenAPI spec, as a new group alongside the
  existing `Timeseries` and `Accounts` tags.

**Rationale**: Mirrors feature 004's §7 reasoning exactly: the metadata endpoint describes a
capability (this endpoint's attribute set), not any one account's data, so it lives outside
the `/v1/accounts/{account_name}/...` item-detail family, as a sibling collection prefix.

**Alternatives considered**: `/v1/accounts/{account_name}/position/attributes` — rejected for
the same reason feature 004 rejected the equivalent nesting: the attribute list never varies
by account, so scoping it under one would be misleading.
