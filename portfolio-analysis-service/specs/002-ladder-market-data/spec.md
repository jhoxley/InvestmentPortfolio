# Feature Specification: Ladder Market Data Enrichment

**Feature Branch**: `002-ladder-market-data`
**Created**: 2026-07-06
**Status**: Draft
**Input**: User description: "extend the /v1/accounts/{account_name}/ladder endpoint of the 'portfolio-analysis-service' to add market data. Given existing functionality expanding a sub-account ledger by date, add three new columns: (1) price, (2) market value, (3) portfolio weight. For the first column a call is made to the 'market-data-web-service' assumed to be running on the same server. Create a configuration entry for 'portfolio-analysis-service' to configure the host/port for the other service. Amend 'run_end_to_end.ps1' steps to ensure this config maps to the instantiated services. Prior to calling the market data service, the code should load a mapping file to go from sub-account name to street identifier that retrieves prices. This mapping exists as a JSON path where each element is keyed off the 'name' field matching the 'sub account' name in input data, this maps to 'isin' or 'ticker' fields that can be input to the market data service. This file should be referenced via configuration file and not in the code. For each distinct sub-account the earliest/latest date should be found from the expanded position ladder and a single call to the market-data-service per sub-account made. Do not run an API call for each individual date, prefer a single or fewer batch requests. For looking up market data the stored position ladder should be assumed to be in GBP currency so all price histories should be requested in this portfolio base currency. It is a key assertion that all daily records in position ladder must have a price that must be in the base currency. If the request to Market Data Service cannot satisfy this then an error occurs indicating which date(s) and sub-accounts had problems. Once a per-date, per-sub-account price in GBP is recorded this is expanded to the second column ('market value') by multiplying the per-unit price by the 'quantity' field. The third column ('portfolio weight') is a post-processing step per date that takes the 'market value' of each sub-account on each date and divides it by the sum of 'market value' across all sub-accounts on the same date. A test assertion is that all rows must have a market value and a portfolio weight. For each date the sum of 'portfolio weight' should always equal 1.0 (aka 100%)."

## Clarifications

### Session 2026-07-06

- Q: How should the Cash sub-account be priced when computing market value and portfolio weight? → A: Synthetic 1.0 GBP, no identifier-mapping entry required and no market-data-service call made for Cash. Matches the existing "Cash Close = 1.0" convention used elsewhere in this codebase.
- Q: Should position ladders already ingested before this feature ships be retroactively enriched with price data? → A: Add a forced-refresh path — resubmitting the exact same (checksum-unchanged) ledger file now triggers re-enrichment (fresh market-data calls to refresh price/market value/weight) instead of being a pure no-op. The underlying ledger rows and date range are not re-expanded; only the price enrichment is recomputed.
- Q: When a sub-account's identifier mapping entry has both `isin` and `ticker` populated, which takes precedence when requesting prices? → A: Prefer `ticker` when both are populated; fall back to `isin` only if `ticker` is absent.
- Q: What should the ingestion response report when a checksum-unchanged re-submission successfully refreshes pricing (per the forced-refresh path)? → A: Still 200 OK, but the response's status value MUST distinguish this "refreshed" outcome from both a brand-new ingestion and a true no-op, so callers can tell pricing was recomputed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View a Priced Position Ladder (Priority: P1)

A developer retrieves a previously ingested position ladder and finds that every daily row for
every sub-account now carries a per-unit price (in GBP), the resulting market value of that
position on that date, and the sub-account's share (portfolio weight) of the account's total
value on that date. This turns the raw quantity ladder into something that can be used directly
for performance and allocation analysis.

**Why this priority**: This is the entire value of the feature — without priced rows, market
value, and weight, the ladder is just a quantity log. Every other story exists to make this one
correct and reliable.

**Independent Test**: Ingest a ledger for an account with two sub-accounts (one equity, one
Cash). Retrieve the resulting ladder and verify every row has a price, market value, and
portfolio weight, that Cash is priced at 1.0 GBP, and that the two sub-accounts' weights sum to
1.0 on every date.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Ingested ladder rows are enriched with price, market value, and weight
  Given a valid sub-account ledger for account "test-portfolio" with sub-accounts
      "Equities A" and "Cash"
  And "Equities A" resolves via the identifier mapping file to a ticker with a complete
      GBP price history covering the ladder's date range
  When the ledger is ingested
  Then every row in the stored ladder has a non-null price, market value, and portfolio weight
  And the Cash sub-account's price is 1.0 on every date
  And each row's market value equals its price multiplied by its quantity

Scenario: Portfolio weight sums to 1.0 on every date
  Given a successfully enriched position ladder for account "test-portfolio" containing
      multiple sub-accounts across multiple dates
  When the portfolio weight column is computed
  Then for every distinct date in the ladder, the sum of portfolio weight across all
      sub-accounts present on that date equals 1.0 (within floating-point tolerance)

Scenario: Re-submitting an unchanged ledger reports a refreshed status
  Given account "test-portfolio" already has an enriched position ladder from a prior ingestion
  When the exact same ledger file (unchanged checksum) is submitted again
  Then the response status is 200 OK
  And the response status value indicates pricing was refreshed, distinct from both a
      brand-new ingestion and a true no-op
  And the ladder's price, market value, and portfolio weight columns reflect newly recomputed
      values
```

---

### User Story 2 - Efficient Batch Price Retrieval Per Sub-Account (Priority: P1)

When enriching a ladder, the system resolves each distinct sub-account's earliest and latest
active date and requests that sub-account's full GBP price history from the market data service
in a single request, rather than requesting a price one date at a time.

**Why this priority**: Without batching, enrichment would issue one market-data call per
(sub-account, date) pair, which is slow, costly, and could overwhelm the market data service.
Batch retrieval is a hard requirement, not an optimisation.

**Independent Test**: Ingest a ledger for an account with one sub-account active across 60
business days. Verify exactly one price-history request is made to the market data service for
that sub-account, covering its full active date range, and zero additional requests are made
for that sub-account.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: One batch request per distinct non-Cash sub-account
  Given a ladder for account "test-portfolio" with sub-account "Equities A" active from
      2024-01-02 through 2024-03-28
  When the ladder is enriched with market data
  Then exactly one price-history request is made to the market data service for the
      identifier mapped to "Equities A"
  And that request's date range spans 2024-01-02 through 2024-03-28
  And no price-history request is made for the "Cash" sub-account

Scenario: Multiple sub-accounts each get their own single batch request
  Given a ladder for account "test-portfolio" with sub-accounts "Equities A" and "Equities B",
      each active over different date ranges
  When the ladder is enriched with market data
  Then exactly one price-history request is made for "Equities A" and exactly one price-history
      request is made for "Equities B"
```

---

### User Story 3 - Fail Fast When GBP Prices Are Incomplete (Priority: P1)

If the market data service cannot supply a GBP price for one or more business days that a
sub-account is active in the ladder, ingestion fails with a descriptive error that identifies
every affected sub-account and every affected date, rather than silently storing a ladder with
missing or wrong-currency prices.

**Why this priority**: A ladder with silent gaps in pricing would produce wrong market values and
wrong portfolio weights downstream. Failing loudly and specifically is essential to trust the
data at all.

**Independent Test**: Ingest a ledger where one sub-account's mapped identifier has a gap in its
GBP price history over part of the ladger's date range. Verify the ingestion request fails, no
ladder is persisted or updated, and the error names the sub-account and the specific missing
date(s).

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Missing GBP price on a business day blocks ingestion
  Given a ledger for account "test-portfolio" with sub-account "Equities A" active from
      2024-01-02 through 2024-01-31
  And the market data service has no GBP price for "Equities A" on 2024-01-15
  When the ledger is ingested
  Then the ingestion request fails with a descriptive error
  And the error identifies "Equities A" and the date 2024-01-15
  And no position ladder is persisted or updated for "test-portfolio"

Scenario: Missing identifier mapping blocks ingestion
  Given a ledger for account "test-portfolio" with sub-account "Equities C"
  And the identifier mapping file has no entry for "Equities C"
  When the ledger is ingested
  Then the ingestion request fails with a descriptive error naming "Equities C"
  And no position ladder is persisted or updated for "test-portfolio"

Scenario: Multiple simultaneous problems are all reported together
  Given a ledger for account "test-portfolio" with sub-accounts "Equities A" and "Equities D"
  And "Equities A" is missing a GBP price on 2024-02-01
  And "Equities D" has no entry in the identifier mapping file
  When the ledger is ingested
  Then the ingestion request fails with a single error response
  And the error identifies both "Equities A" (with date 2024-02-01) and "Equities D"
      (missing mapping) in the same response
```

---

### User Story 4 - Configure Market Data Service Location and Identifier Mapping (Priority: P2)

An operator configures where the market data service is running (host and port) and where the
sub-account-to-identifier mapping file lives, without touching application code. When the
end-to-end run script starts both services, the portfolio-analysis-service's configuration
correctly points at the market data service instance it just started.

**Why this priority**: This is what makes the feature deployable and testable end-to-end; without
it the integration only works if values happen to be hard-coded correctly.

**Independent Test**: Change the configured market data service port and identifier mapping file
path to alternate valid values, restart the service, and confirm ingestion still successfully
enriches a ladder using the newly configured location and mapping.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Market data service location is read from configuration
  Given portfolio-analysis-service is configured with a market data service host and port
      pointing at a running instance
  When a ledger is ingested for an account requiring market data
  Then the price-history requests are sent to the configured host and port

Scenario: Identifier mapping file path is read from configuration
  Given portfolio-analysis-service is configured with a path to an identifier mapping file
  When a ledger is ingested
  Then the sub-account-to-identifier lookups are read from the file at that configured path

Scenario: End-to-end script wires the two services together
  Given the end-to-end run script starts the market-data-web-service on a given host and port
  When the same script starts portfolio-analysis-service
  Then portfolio-analysis-service's configured market data service host and port match where
      market-data-web-service was actually started
```

---

### Edge Cases

- What happens when a sub-account's identifier mapping entry has neither an `isin` nor a
  `ticker` populated? → Treated the same as a missing mapping entry: ingestion fails, naming
  the sub-account.
- What happens when the identifier mapping file itself is missing, unreadable, or not valid
  JSON? → Ingestion fails with a descriptive configuration error; this is a service-level
  problem distinct from a single sub-account's missing entry.
- What happens when the market data service is unreachable (network/connection failure) rather
  than simply missing data? → Ingestion fails with a descriptive error identifying the
  sub-account(s) whose request could not be completed and the underlying cause.
- What happens when an account's total market value across all sub-accounts is zero on a given
  date (e.g. all balances are zero)? → Portfolio weight cannot be meaningfully computed by
  division; every sub-account's weight for that date is recorded as 0, and this date is exempt
  from the "weights sum to 1.0" success criterion.
- What happens when the market data service returns a price for a date that is a business day
  in the ladder but a market holiday for the underlying security? → Treated as a missing price
  for that date; it triggers the same fail-fast behavior as any other pricing gap — no
  forward-filling of prices across gaps.
- What happens when the same ledger file (unchanged checksum) is re-submitted for an account
  that already has an enriched ladder? → The ladder's rows and date range are not re-expanded,
  but price, market value, and portfolio weight are recomputed via fresh market-data-service
  calls, replacing the previously stored values. The response is 200 OK with a status value that
  distinguishes this "refreshed" outcome from a true no-op.
- What happens to the Cash sub-account? → Always priced at 1.0 GBP; no identifier mapping
  lookup or market-data-service call is made for Cash.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST extend the position ladder with three additional columns for
  every row: `price` (per-unit price in GBP), `market_value`, and `portfolio_weight`.
- **FR-002**: The system MUST load a sub-account-to-identifier mapping from a JSON file, keyed
  by a `name` field matching sub-account names, providing an `isin` and/or `ticker` field usable
  to request prices from the market data service. The path to this file MUST be provided via
  configuration, not hard-coded.
- **FR-003**: The system MUST provide a configuration entry for the market data service's host
  and port; this MUST NOT be hard-coded.
- **FR-004**: The Cash sub-account MUST be priced at a fixed 1.0 GBP for every date, without
  requiring an identifier mapping entry or a market-data-service call.
- **FR-005**: For every distinct non-Cash sub-account present in a ladder being enriched, the
  system MUST resolve its identifier via the mapping file. If no mapping entry exists, or the
  entry has neither `isin` nor `ticker` populated, ingestion MUST fail with an error identifying
  the affected sub-account(s). When a mapping entry has both `ticker` and `isin` populated, the
  system MUST use `ticker` to request prices; `isin` MUST only be used when `ticker` is absent.
- **FR-006**: For every distinct non-Cash sub-account, the system MUST determine that
  sub-account's earliest and latest active date within the ladder being enriched, and MUST
  request its GBP price history from the market data service as a single request covering that
  full date range. The system MUST NOT issue one price request per individual date.
- **FR-007**: All price history requests MUST specify GBP as the requested currency, matching
  the portfolio's fixed base currency.
- **FR-008**: The system MUST validate that a GBP price is available for every business-day row
  of every sub-account in the ladder being enriched. If any row cannot be priced, ingestion MUST
  fail without persisting or updating the stored ladder, and the resulting error MUST identify
  every affected sub-account together with every affected date, in a single response.
- **FR-009**: For every successfully priced row, the system MUST compute `market_value` as
  `price × quantity`.
- **FR-010**: For every date present in an enriched ladder, the system MUST compute each
  sub-account's `portfolio_weight` as that sub-account's `market_value` divided by the sum of
  `market_value` across all sub-accounts present on that same date, except where that sum is
  zero (see Edge Cases), in which case `portfolio_weight` is recorded as 0 for that date.
- **FR-011**: Every row of a successfully enriched ladder MUST have a non-null `market_value`
  and `portfolio_weight`.
- **FR-012**: For every date in a successfully enriched ladder where the total market value
  across sub-accounts is non-zero, the sum of `portfolio_weight` across all sub-accounts present
  on that date MUST equal 1.0 within floating-point tolerance.
- **FR-013**: Re-submitting a ledger file whose checksum is unchanged from the existing stored
  ladder MUST recompute price, market value, and portfolio weight via fresh market-data-service
  calls (following FR-005 through FR-012), without re-expanding the underlying ladder rows or
  date range. The response MUST remain 200 OK, and its status indicator MUST distinguish this
  "refreshed" outcome from both a brand-new ingestion and a true no-op, so callers can tell that
  pricing was recomputed even though the ledger content did not change.
- **FR-014**: The end-to-end run script MUST be updated so that the market data service
  host/port configured for portfolio-analysis-service matches the host/port the script actually
  starts the market data service on.

### Key Entities

- **Identifier Mapping File**: A configured JSON file mapping sub-account `name` to a street
  identifier (`isin` and/or `ticker`) usable to request prices from the market data service.
- **Market Data Service**: An external, separately-running service queried for historical
  per-identifier prices in a specified currency over a date range.
- **Priced Ladder Row**: An existing position ladder row (date, sub-account, quantity, etc.)
  extended with `price`, `market_value`, and `portfolio_weight`.
- **Portfolio Weight**: A per-date, per-sub-account proportion of that date's total account
  market value, expressed as a fraction that sums to 1.0 across all sub-accounts on that date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of rows in a successfully enriched ladder contain a price, market value, and
  portfolio weight — verified across all sub-accounts and dates in the test data set.
- **SC-002**: For every date in a successfully enriched ladder (excluding zero-total-value
  dates), the sum of portfolio weight across all sub-accounts equals 1.0 within a tolerance of
  0.0001.
- **SC-003**: The number of market-data-service price-history requests made during a single
  ingestion never exceeds one per distinct non-Cash sub-account in that ladder, regardless of
  how many business days that sub-account spans.
- **SC-004**: When any sub-account or date cannot be priced in GBP, the resulting error message
  identifies every affected sub-account and date in a single response, so the issue can be
  diagnosed without additional round trips.
- **SC-005**: Operators can point portfolio-analysis-service at a different market data service
  location or identifier mapping file purely through configuration changes, with no code
  modification required.

## Assumptions

- The portfolio's base currency is fixed as GBP for all accounts processed by this service; all
  price history requests specify GBP as the target currency.
- The market data service (`market-data-web-service`) is reachable over HTTP from
  portfolio-analysis-service, typically on the same host, consistent with this repository's
  existing trusted-local-service pattern (no authentication between the two services).
- The identifier mapping file follows the same shape as the legacy static JSON configuration
  described in this repository's root documentation (an array of objects keyed by `name`, with
  `isin` and `ticker` fields); only the `name` → identifier resolution is consumed by this
  feature. Other fields present in that file (e.g. `theme`, `multiplier`, `ignore`) are not
  used by this feature.
- Enrichment (price, market value, portfolio weight) is computed as part of the existing
  ingestion pipeline, when a ledger is submitted (new, changed, or checksum-unchanged
  re-submission per FR-013) — it is not recomputed on every read of an already-enriched ladder.
- "Distinct sub-account" date range (for the single batch price request) is scoped to that
  sub-account's own earliest and latest active date within the ladder being enriched, not the
  account's overall date range.
- A floating-point tolerance of 0.0001 is applied when asserting that portfolio weights sum to
  1.0 for a given date.
- Failure to price any single row causes the entire ingestion request to fail; there is no
  partial enrichment where some sub-accounts or dates succeed and others are silently left
  unpriced.
- FR-013 supersedes feature 001's FR-007 idempotency guarantee ("without reprocessing," "the
  stored XLSX file is unchanged" on checksum match). A checksum-unchanged re-submission is no
  longer a pure no-op: it now always triggers fresh market-data calls and rewrites `ladder.xlsx`
  with refreshed pricing. Feature 001's `spec.md` is left as an unedited historical record of
  that feature's original scope; the corresponding stale test scenario in
  `tests/features/ingest_ladder.feature` is updated as part of this feature's implementation
  (see tasks.md) rather than by editing feature 001's spec.
