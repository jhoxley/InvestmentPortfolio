# Phase 0 Research: Capital Ledger Ingestion

All unknowns from the feature spec were resolvable from the existing codebase (feature 001's
ladder ingestion, feature 002's market-data enrichment) and the reference input file
(`HL_SIPP_Capital_Ledger.xlsx`). No external technology research was required — this feature adds
one more resource type to an existing FastAPI service using its existing stack (Python 3.11,
FastAPI, pandas, openpyxl, structlog, Pydantic).

## 1. How to literally reuse the sub-account ledger's expansion code/logic

**Decision**: Extract the calendar-reindex + forward-fill core of `LadderExpander.expand()` into
a shared helper, `app/services/business_day_expansion.py::expand_business_days()`, that both
`LadderExpander` (unchanged behaviour, refactored to delegate) and the new
`CapitalLedgerExpander` call.

**Rationale**: The spec explicitly asks to "use the same code/logic as for expanding the
sub-account ledger," not merely produce equivalent output. `LadderExpander`'s per-sub-account
block already does exactly what the capital ledger needs (reindex over calendar days, forward-fill,
filter down to business days) — the only differences are (a) the ladder groups by `sub_account`
and applies a closure rule per group, while the capital ledger is a single flat series with
no grouping or closure rule, and (b) the two use a different end-of-range boundary (see research
item 2). Extracting the shared mechanic keeps both call sites honest about using one
implementation, satisfies the constitution's SOLID/DRY expectations, and is a safe,
behaviour-preserving refactor of `LadderExpander` (its existing unit tests in
`test_ladder_expander.py` continue to assert the same outputs).

**Alternatives considered**:
- Copy the reindex/ffill block into a new, independent `CapitalLedgerExpander` — rejected: two
  copies of the same logic drift apart over time and contradict the spec's explicit "same
  code/logic" instruction.
- Make `CapitalLedgerExpander` call `LadderExpander` directly (e.g., by wrapping the input in a
  single synthetic "sub_account") — rejected: conflates two different domain concepts (a capital
  ledger has no sub-account dimension) and would carry over the closure rule inappropriately.

## 2. Expansion end-of-range boundary

**Decision**: The capital ledger's expansion range is `[min(date), max(date)]` as recorded in the
*submitted file itself*. No `today` parameter is threaded into `CapitalLedgerExpander` at all.

**Rationale**: The spec explicitly states expansion covers "every business day … between the
earliest and latest date recorded" — a closed, historical range. This is a deliberate departure
from `LadderExpander`, whose range extends forward to "today minus two business days" specifically
to support the market-data pricing step added in feature 002. The capital ledger has no pricing
step (see research item 3), so there is no freshness boundary to honor, and extending it to
"today" would fabricate rows beyond what the source ledger actually records.

**Alternatives considered**:
- Reuse the ladder's `today - 2 business days` boundary for consistency — rejected: contradicts
  the explicit instruction and would silently extend the stored ledger with fabricated
  forward-filled rows the account may not actually be able to justify (e.g., after the source
  system's last export).

## 3. Whether capital ingestion needs market-data enrichment

**Decision**: No. `CapitalIngestionService` is validate → expand → persist only; no
`PricingEnrichmentService`, `MarketDataClient`, or `IdentifierMappingRepository` dependency.

**Rationale**: `create_capital_ledger`'s output (`capital`, `income`, `book_value`) is already
fully expressed in the account's base currency — confirmed by inspecting the reference file and
the pipeline's `CapitalLedgerEngine`, which sums `Transaction Value` figures directly with no unit
conversion or per-position pricing step. There is nothing analogous to the ladder's
price/market_value/portfolio_weight columns to compute.

**Alternatives considered**: Mirror the ladder's enrichment step for symmetry — rejected as
speculative scope creep; nothing in the request or the reference data calls for it, and it would
introduce an unused dependency on the market-data service for this endpoint.

## 4. Error handling: new exception classes vs. reusing existing ones

**Decision**: Reuse `AccountNotFoundError` (404) and `MergeNotSupportedError` (409) as-is, passing
a capital-specific `message` override at the call site. Add exactly one new exception,
`EmptyCapitalDateRangeError` (422), plus one new handler in `main.py`.

**Rationale**: Both reused exceptions already accept an optional `message` override and their
FastAPI `@app.exception_handler` registrations key purely on exception *type* — the handler code
is 100% generic (logs, builds an RFC 7807 problem, returns the right status). Adding
`CapitalAccountNotFoundError` / `CapitalMergeNotSupportedError` subclasses would duplicate two
handlers that behave identically, for no behavioural gain. The empty-date-range case, however,
carries genuinely different semantics — `EmptyDateRangeError` is documented and worded in terms
of "within two business days of today," which doesn't apply to a range bounded by recorded data
only — so it gets its own exception type and message rather than being force-fitted into the
existing one.

**Alternatives considered**: One generic `EmptyDateRangeError` parameterized to cover both cases —
rejected: the two constructors would need mutually-exclusive optional parameters ("today" for one
caller, "latest_date" for the other), which is a worse interface than two small, honestly-named
exceptions.

## 5. Storage layout

**Decision**: `data/{account_name}/capital.xlsx` + `data/{account_name}/capital_meta.json`,
siblings of the existing `ladder.xlsx` / `meta.json` in the same per-account directory.

**Rationale**: Matches "store it in the same `.\Data\` location by account name" literally, while
keeping the capital ledger's checksum/row-count/date-range lifecycle completely independent of any
stored position ladder for the same account (FR-011) — a distinct filename and a distinct meta
file mean ingesting one never touches the other's state.

**Alternatives considered**: A nested `data/{account_name}/capital/` subdirectory — rejected as
unneeded extra nesting; flat sibling files are simpler and match the existing convention (a single
`ladder.xlsx` + `meta.json` pair per account today).

## 6. API surface and routing

**Decision**: New router `app/api/capital.py`, registered in `main.py` alongside the existing
`ladder` router, exposing:
- `POST /v1/accounts/{account_name}/capital`
- `GET /v1/accounts/{account_name}/capital`
- `GET /v1/accounts/{account_name}/capital/download`

**Rationale**: Directly mirrors the ladder endpoints' path shape (per FR-001), account-name
validation, and response conventions (HATEOAS `_links`, RFC 7807 errors), satisfying Constitution
principle V. Because there is no market-data dependency, the router's DI wiring is simpler than
`ladder.py`'s (no `MarketDataClient` / `IdentifierMappingRepository` providers needed).

**Alternatives considered**: Add capital routes to the existing `ladder.py` router/file —
rejected: violates Single Responsibility (the ladder router is already the pricing-enriched
position-ladder concern); a separate module keeps the two resource types independently
extensible (Open/Closed).
