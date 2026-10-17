# Feature Specification: Position & Portfolio-Weighted Daily Returns

**Feature Branch**: `006-ladder-daily-returns`
**Created**: 2026-07-26
**Status**: Draft
**Input**: User description: "When ingesting the sub-account ledger to build a position ladder via POST /v1/accounts/{account_name}/ladder we need to calculate a daily position return and a portfolio weighted daily position return. The calculation for the position return on a ladder date is the price on that date minus the price on the previous date plus any income per share on the ladder, all divided by the previous date's price. Income per share can be derived from the existing 'total_income' field: this ladder date's total_income minus the previous ladder date's total_income divided by the quantity on the current ladder date. The portfolio weighted daily return is the position return multiplied by the portfolio_weight field. These two metrics should be calcualted on ingestion and stored locally for retrieval at a later date. Handling for the first trade date in a position should be to assume a zero return on the first ladder date where no prior records exist."

## Clarifications

### Session 2026-07-26

- Q: Should this feature also expose the new metrics through the existing position time series retrieval API, or is it scoped to computing and persisting them during ingestion only? → A: Storage + API exposure — extend the `attribute` enum on `GET /v1/accounts/{account_name}/position` (and the attribute metadata endpoint) so the new metrics are retrievable through the existing endpoint, in addition to being computed and persisted during ingestion.

### Correction 2026-07-26

- The initial draft of this spec computed `weighted_position_return` as `position_return *
  portfolio_weight`, using the *same-date* `portfolio_weight`. This was incorrect: accurate
  return attribution requires the *start-of-day* weight, i.e. the `portfolio_weight` recorded
  on the sub-account's *previous* ladder date (T-1). The spec (User Story 2, FR-003, Key
  Entities, Edge Cases, Success Criteria, Assumptions) has been corrected accordingly. The
  `position_return` formula itself (User Story 1, FR-001, FR-002) is unaffected — only the
  weighting step changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily Return Recorded for Every Priced Position (Priority: P1)

A developer ingests a sub-account ledger and, once ingestion completes, finds that every daily
row of the resulting position ladder carries a per-position daily return: the price change plus
any per-share income earned that day, expressed as a fraction of the previous day's price. This
turns the priced ladder into something usable directly for performance analysis without
re-deriving returns from raw price and income history on every read.

**Why this priority**: This is the core value of the feature — without a correctly computed
daily return, no other part of the feature (weighting, retrieval) has anything to operate on.

**Independent Test**: Ingest a ledger for an account with one non-Cash sub-account active across
several consecutive business days with varying prices and at least one income event. Retrieve
the resulting ladder and verify each row's `position_return` equals
`(price_t - price_{t-1} + income_per_share_t) / price_{t-1}`, where
`income_per_share_t = (total_income_t - total_income_{t-1}) / quantity_t`.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Daily position return reflects price change and income
  Given a priced position ladder for account "test-portfolio" with sub-account "Equities A"
      active on consecutive business days 2024-01-02 through 2024-01-05
  And "Equities A" has price 100.0 on 2024-01-02, 102.0 on 2024-01-03, 101.0 on 2024-01-04,
      and 103.0 on 2024-01-05
  And "Equities A" has total_income 0.0 through 2024-01-03, then 5.0 from 2024-01-04 onward,
      with quantity 10.0 on every date
  When the ledger is ingested
  Then the row for 2024-01-03 has position_return equal to (102.0 - 100.0 + 0.0) / 100.0
  And the row for 2024-01-04 has position_return equal to (101.0 - 102.0 + 0.5) / 102.0
  And the row for 2024-01-05 has position_return equal to (103.0 - 101.0 + 0.0) / 101.0

Scenario: First recorded date for a position has zero return
  Given a priced position ladder for account "test-portfolio" with sub-account "Equities B"
      first appearing on 2024-02-01 (no prior row exists for "Equities B")
  When the ledger is ingested
  Then the row for "Equities B" on 2024-02-01 has position_return equal to 0.0
```

---

### User Story 2 - Portfolio-Weighted Return for Allocation-Level Analysis (Priority: P1)

A developer retrieves the position ladder and finds that each row also carries a
portfolio-weighted daily return — the position's own daily return scaled by its start-of-day
share of the account's total value, i.e. the `portfolio_weight` recorded on the *previous*
ladder date (T-1), not the date the return itself is for — so that individual position returns
can be summed across an account or theme to analyse contribution to overall performance. Using
the start-of-day weight is what makes the weighted figure a correct contribution measure: the
weight in effect going into the day is what determines how much of the account's value that
day's return applies to, not the weight that results after the day's price move has already
happened.

**Why this priority**: Without the weighted figure, comparing or aggregating returns across
positions of different sizes is meaningless; this is what makes the raw return usable at the
account level. Using the same-day weight instead of the start-of-day weight would silently
produce contribution figures that don't correctly attribute to the account's actual return.

**Independent Test**: Ingest a ledger for an account with two sub-accounts across two
consecutive dates. Verify each row's `weighted_position_return` equals `position_return *
portfolio_weight`, where the `portfolio_weight` used is the value recorded on that
sub-account's *previous* ladder date, not the row's own date.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Weighted return uses the previous date's (start-of-day) portfolio weight
  Given a priced position ladder for account "test-portfolio" with sub-accounts "Equities A"
      and "Equities B" both present on 2024-03-03 and 2024-03-04
  And on 2024-03-03, "Equities A" has portfolio_weight 0.55 and "Equities B" has
      portfolio_weight 0.45
  And on 2024-03-04, "Equities A" has position_return 0.02 and portfolio_weight 0.6
  And on 2024-03-04, "Equities B" has position_return -0.01 and portfolio_weight 0.4
  When the ladder is ingested
  Then the "Equities A" row for 2024-03-04 has weighted_position_return equal to
      0.02 multiplied by its 2024-03-03 portfolio_weight of 0.55 (i.e. 0.011), not by its
      own-date portfolio_weight of 0.6
  And the "Equities B" row for 2024-03-04 has weighted_position_return equal to
      -0.01 multiplied by its 2024-03-03 portfolio_weight of 0.45 (i.e. -0.0045), not by its
      own-date portfolio_weight of 0.4

Scenario: First recorded date for a position has zero weighted return
  Given a priced position ladder for account "test-portfolio" with sub-account "Equities B"
      first appearing on 2024-02-01 (no prior row, and therefore no prior portfolio_weight,
      exists for "Equities B")
  When the ladder is ingested
  Then the row for "Equities B" on 2024-02-01 has weighted_position_return equal to 0.0
```

---

### User Story 3 - Returns Are Computed Once, at Ingestion Time (Priority: P1)

Both metrics are calculated during ingestion and persisted with the rest of the position ladder,
so retrieving them later is a plain read rather than a recomputation, consistent with how price,
market value, and portfolio weight already work.

**Why this priority**: Without persistence, every read would need to re-derive returns from
scratch, which is wasteful and risks inconsistent results between reads if the underlying
computation ever depends on more than the current row.

**Independent Test**: Ingest a ledger once, then issue two separate retrieval requests for the
same account/date range. Verify both requests return identical `position_return` and
`weighted_position_return` values without a further ingestion call in between, and verify (via
timing or an accessible ingestion log/counter) that no market-data or recomputation work happens
on the second read.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Returns are stable across repeated reads without re-ingestion
  Given a priced and return-enriched position ladder already ingested for account
      "test-portfolio"
  When the position time series is retrieved twice in a row for the same account, positions,
      attributes, and date range
  Then both responses report identical position_return and weighted_position_return values
      for every matching row
```

---

### User Story 4 - Retrieve Returns Through the Position Time Series API (Priority: P2)

A developer requests `position_return` and/or `weighted_position_return` as attributes from the
existing position time series endpoint, the same way they already request `market_value` or
`quantity`, and receives them alongside any other requested attributes for the same rows.

**Why this priority**: Computing and storing the metrics has no external value until they can
actually be retrieved through the service's existing API surface; this closes the loop opened by
User Story 1–3.

**Independent Test**: Ingest a return-enriched ladder, then call the position time series
endpoint requesting `attribute=position_return&attribute=weighted_position_return`. Verify the
response includes both attributes on each entry, and that the attribute metadata endpoint
describes both new attributes.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Position and weighted returns are retrievable as time series attributes
  Given a return-enriched position ladder for account "test-portfolio" with sub-account
      "Equities A" active on 2024-01-02 through 2024-01-05
  When a request is made for
      "/v1/accounts/test-portfolio/position?position=Equities A&attribute=position_return&attribute=weighted_position_return"
  Then the response entries for "Equities A" each include a position_return value and a
      weighted_position_return value matching the values stored at ingestion

Scenario: New attributes appear in attribute metadata
  When a request is made for "/v1/positions/attributes"
  Then the response includes an entry named "position_return" and an entry named
      "weighted_position_return", each with a description and a source
```

---

### Edge Cases

- What happens when the current ladder date's `quantity` is zero (e.g. a position fully
  divested on that date)? → Income per share cannot be computed by division; it is treated as
  0 for that date's return calculation, avoiding a division-by-zero rather than failing
  ingestion.
- What happens when the previous ladder date's `price` is zero? → Existing ingestion guarantees
  (feature 002) require every priced row to have a non-null, non-zero price in the portfolio's
  base currency, so this condition should not occur for successfully priced ladders; if it were
  to occur, that row's `position_return` and `weighted_position_return` are recorded as 0 rather
  than raising a division error, consistent with the fail-soft handling of the zero-quantity
  case above.
- What happens on the very first ladder date recorded for a given sub-account (no prior row to
  compare against, and therefore no prior `portfolio_weight` to use as the start-of-day
  weight)? → `position_return` and `weighted_position_return` are both recorded as 0.0, per the
  feature's explicit first-trade-date rule. This also covers the "no previous portfolio_weight
  exists" case for the weighted metric — there is no need to separately guard against a missing
  T-1 weight, since the same first-date rule already forces the weighted result to 0.0.
- What happens when a sub-account has a gap in its ladder history (e.g. fully divested, then
  re-purchased later)? → The re-entry date is treated the same as any other first appearance
  with no prior row immediately preceding it in that sub-account's own row sequence: both
  `position_return` and `weighted_position_return` are 0.0 on that date (the row before the gap
  is not used as a T-1 source for either the price/income calculation or the start-of-day
  weight), and normal calculation resumes from the following date.
- What happens for the "Cash" sub-account? → The same formula applies uniformly; since Cash's
  price is fixed at 1.0 GBP (feature 002) and Cash ordinarily has no income, this naturally
  yields a return of 0.0 on every date without any special-cased logic.
- What happens when a ledger with a previously-enriched (return-bearing) ladder is
  re-submitted (checksum-unchanged forced refresh, per feature 002)? → Both return metrics are
  recomputed from the freshly recomputed price/income/quantity/weight values, replacing the
  previously stored figures, consistent with feature 002's existing refresh behaviour.
- What happens when the upstream price-enrichment step itself fails (e.g. a sub-account has no
  usable identifier-mapping entry, or a GBP price cannot be obtained for one or more business
  days — feature 002's `IdentifierMappingError`/`PriceCoverageError`)? → Ingestion fails before
  return computation is ever reached; no ladder (and therefore no `position_return`/
  `weighted_position_return` values) is persisted or updated for that account, inheriting feature
  002's existing fail-fast, no-partial-ladder behaviour unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute, for every row of a position ladder being ingested, a
  `position_return` value equal to
  `(price_t - price_{t-1} + income_per_share_t) / price_{t-1}`, where `price_t` and `price_{t-1}`
  are that sub-account's price on the current and immediately preceding ladder date
  respectively.
- **FR-002**: The system MUST compute `income_per_share_t` as
  `(total_income_t - total_income_{t-1}) / quantity_t`, using the current and immediately
  preceding ladder date's `total_income` for that sub-account and the current ladder date's
  `quantity`.
- **FR-003**: The system MUST compute, for every row, a `weighted_position_return` value equal
  to `position_return_t * portfolio_weight_{t-1}` — the current row's `position_return`
  multiplied by that sub-account's `portfolio_weight` from the *immediately preceding* ladder
  date (its start-of-day weight), not the `portfolio_weight` recorded on the row's own date.
- **FR-004**: For the first ladder date recorded for a given sub-account (no preceding row for
  that sub-account exists, and therefore no preceding `portfolio_weight` to use as the
  start-of-day weight), the system MUST record `position_return` and `weighted_position_return`
  as 0.0 rather than attempting the full calculation.
- **FR-005**: When the current ladder date's `quantity` for a sub-account is zero, the system
  MUST treat `income_per_share_t` as 0 for that date's calculation rather than dividing by zero.
- **FR-006**: `position_return` and `weighted_position_return` MUST be computed as part of the
  same ingestion pipeline that computes `price`, `market_value`, and `portfolio_weight`
  (feature 002), including on a checksum-unchanged forced-refresh re-submission, so that both
  metrics are always derived from the currently-stored price, income, quantity, and weight
  values.
- **FR-007**: The system MUST persist `position_return` and `weighted_position_return` as part
  of the stored position ladder, so that retrieving them later does not require recomputation.
- **FR-008**: The position time series retrieval endpoint (`GET
  /v1/accounts/{account_name}/position`) MUST accept `position_return` and
  `weighted_position_return` as valid values of its `attribute` query parameter, returning the
  stored values for the requested positions and date range on the same terms as existing
  attributes (e.g. `market_value`, `quantity`).
- **FR-009**: The attribute metadata endpoint (`GET /v1/positions/attributes`) MUST describe
  `position_return` and `weighted_position_return` alongside the existing attributes, including
  a human-readable description and source for each.

### Key Entities

- **Position Return**: A per-date, per-sub-account fraction expressing that position's price
  change plus per-share income for the day, relative to the previous day's price. Zero on a
  sub-account's first recorded ladder date.
- **Weighted Position Return**: A per-date, per-sub-account fraction equal to that date's
  Position Return scaled by the sub-account's *start-of-day* Portfolio Weight (feature 002) —
  i.e. the Portfolio Weight recorded on the immediately preceding ladder date, not the row's own
  date — usable for account- or theme-level contribution analysis.
- **Income Per Share**: An intermediate, per-date, per-sub-account value derived from the change
  in `total_income` since the previous ladder date, divided by the current date's `quantity`;
  not persisted as its own column, only used to compute Position Return.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of rows in a successfully ingested position ladder contain a
  `position_return` and a `weighted_position_return` value — verified across all sub-accounts
  and dates in the test data set.
- **SC-002**: For every sub-account's first recorded ladder date, `position_return` and
  `weighted_position_return` are exactly 0.0 — verified across all sub-accounts in the test
  data set, including a sub-account that re-enters the ladder after a gap.
- **SC-003**: For non-first-date rows, `position_return` and `weighted_position_return` match a
  hand-computed expected outcome — verified against a hand-computed set of prices, income
  events, quantities, and portfolio weights covering price increases, price decreases,
  zero-income days, and at least one case where a sub-account's `portfolio_weight` changes from
  one date to the next (to confirm the weighted return uses the previous date's weight, not the
  current date's).
- **SC-004**: Retrieving the same account's ladder twice in succession returns identical
  `position_return` and `weighted_position_return` values both times, with no ingestion call
  between the two retrievals.
- **SC-005**: A caller can retrieve `position_return` and `weighted_position_return` through the
  existing position time series endpoint using the same request pattern as any other supported
  attribute, and the attribute metadata endpoint documents both.

## Assumptions

- Both metrics apply uniformly to every sub-account present in the ladder, including "Cash";
  no sub-account is exempt from the calculation or requires special-cased logic, since the
  formula naturally yields 0.0 for Cash under its existing fixed-price, no-income treatment.
- "Previous ladder date" means the immediately preceding row for that same sub-account in the
  ladder's own date sequence (which, per feature 001, is already expanded to consecutive
  business days while the position is active) — not the previous calendar day and not the
  previous row for a different sub-account. This applies consistently to both the
  `position_return` calculation (previous `price` and `total_income`) and the
  `weighted_position_return` calculation (previous `portfolio_weight`).
- `weighted_position_return` intentionally uses the previous ladder date's `portfolio_weight`
  (the start-of-day weight) rather than the current date's, so that the weighting reflects the
  account allocation in effect *before* that day's price movement, not after it. This mirrors
  standard portfolio-attribution practice, where a period's contribution is weighted by the
  allocation held at the start of the period, not its end.
- These metrics depend on `price`, `total_income`, `quantity`, and `portfolio_weight` all being
  present on both the current and previous rows; since ingestion already requires every row of a
  successfully priced ladder to carry non-null `price` and `portfolio_weight` (feature 002),
  this feature does not need to separately validate those preconditions.
- A checksum-unchanged forced-refresh re-submission (feature 002) recomputes both new metrics
  alongside price, market value, and portfolio weight — there is no separate "returns changed
  independently of pricing" scenario, since both metrics are pure functions of already-stored
  ladder columns.
- No new persisted column is introduced for `income_per_share`; it is an intermediate value
  computed and discarded during the `position_return` calculation.
- Floating-point comparisons for return values in tests use a small absolute tolerance (e.g.
  `abs_tol=1e-9`), consistent with this codebase's existing floating-point test conventions.
