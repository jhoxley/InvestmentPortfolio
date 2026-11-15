# Feature Specification: VaR Contributions (Marginal Risk) Endpoint

**Feature Branch**: `015-var-contributions`
**Created**: 2026-11-15
**Status**: Draft
**Input**: User description: "Add a read-only Value at Risk contributions endpoint to the risk endpoint group, built on the historical-simulation engine from feature 012. For a given account, as-of date, look-back (1y/2y/5y, default the configured headline) and confidence level, compute the scenario x position PnL matrix (today's GBP market value times each held position's aligned historical return, using the same scenario construction, proxy/rescale treatment and quality rules as the existing VaR calculation) and report each position's contribution to risk, grouped by position or by theme (group_by=position|theme). For each group report: standalone VaR, incremental VaR, component ES, and marginal VaR. Also report each group's market value, weight, and coverage/quality. The endpoint is GET /v1/accounts/{account}/risk/var/contributions with query parameters date, lookback, confidence, and group_by. Must not require a new calculation run: reuse the aligned scenario returns already available from the most recent successful run, persisting the aligned returns snapshot so this endpoint needs no market-data calls. If no run has computed that account/date/look-back combination, return the same 'not computed' shape used by the existing VaR series endpoint. If the date's VaR quality is insufficient, return the same insufficient-quality signal. Validation errors reuse invalid-var-lookback and invalid-confidence-level, plus a new invalid-group-by. This feature does NOT add what-if/hypothetical-holdings evaluation and does NOT add combined-account VaR — both deferred to a later feature. Methodology reference: docs/proposals/value-at-risk.md section 8."

## Clarifications

### Session 2026-11-15

- Q: How should the synthetic Cash position be treated in the contributions breakdown? → A: Include Cash as its own group (position row, and its own "Cash" theme when grouping by theme), with standalone/incremental/component/marginal VaR all ≈0, but counted in market value and weight.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See which positions drive an account's risk on a given date (Priority: P1)

As a portfolio owner reviewing an account's VaR, I want to see which individual positions contribute
most to the total loss estimate on a chosen date, so I know where the account's risk is concentrated
rather than just the single portfolio-level number.

**Why this priority**: This is the core value of the feature — the headline VaR number alone (already
available from feature 013) doesn't say *why* the risk is what it is. Without this breakdown the user
cannot act on the VaR figure at all.

**Independent Test**: For an account and date that already has a completed VaR run, request the
contributions endpoint grouped by position and confirm the reported component contributions sum
(within rounding) to the account's total Expected Shortfall for that date/lookback/confidence, and
that the position with the largest component is sensibly identifiable.

**Acceptance Scenarios**:

```gherkin
Scenario: Contributions grouped by position for a fully computed date
  Given account "HL-SIPP" has a completed VaR run covering 2026-09-22 at lookback "2y"
  When a client requests GET /v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&lookback=2y&confidence=0.99&group_by=position
  Then the response returns 200 with one entry per held position
  And each entry reports standalone VaR, incremental VaR, component ES, marginal VaR, market value, weight and quality
  And the sum of component ES across all entries equals the account's total ES at that date/lookback/confidence within a small rounding tolerance

Scenario: Contributions grouped by theme
  Given account "HL-SIPP" has a completed VaR run covering 2026-09-22 at lookback "2y"
  When a client requests GET /v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&lookback=2y&confidence=0.99&group_by=theme
  Then the response returns 200 with one entry per theme present in the account's holdings on that date
  And each theme entry aggregates the market value and contributions of the positions mapped to it
```

---

### User Story 2 - Understand risk when data for the request is missing or degraded (Priority: P2)

As a user of the Risk page, when I ask for contributions on a date or lookback that hasn't been
computed yet, or where the VaR itself is of insufficient quality, I want a clear, non-error response
telling me that rather than a confusing failure or fabricated numbers.

**Why this priority**: Without this, the UI (feature 027/F) cannot distinguish "nothing to show yet"
from a real system fault, and a user could be shown misleading contribution figures built on
insufficient data.

**Independent Test**: Request contributions for an account/date/lookback combination that has never
been run, and separately for a date whose stored VaR quality is `insufficient`, and confirm each
returns the documented non-fabricated response rather than a 4xx/5xx error or invented numbers.

**Acceptance Scenarios**:

```gherkin
Scenario: No VaR run has ever covered the requested account and lookback
  Given account "HL-ISA" has never had a VaR run
  When a client requests GET /v1/accounts/HL-ISA/risk/var/contributions?date=2026-09-22&lookback=2y&confidence=0.99
  Then the response returns 200 with an empty contributions payload
  And the response includes links to the account's VaR status and runs resources

Scenario: The requested date's VaR quality is insufficient
  Given account "HL-SIPP" has a VaR estimate for 2016-05-03 at lookback "5y" with quality "insufficient"
  When a client requests GET /v1/accounts/HL-SIPP/risk/var/contributions?date=2016-05-03&lookback=5y&confidence=0.99
  Then the response returns 200 with the same insufficient-quality signal used by the VaR series endpoint
  And no standalone, incremental, component or marginal values are reported for that date
```

---

### User Story 3 - Reject malformed requests clearly (Priority: P3)

As an API client, if I send an invalid lookback, confidence level or grouping, I want a clear,
structured error telling me exactly what was wrong, consistent with how the existing VaR endpoints
report such errors.

**Why this priority**: Lower priority than the two data-shape scenarios above because it only affects
malformed requests, but it keeps the new endpoint consistent with the rest of the risk API's error
handling, which the UI and other clients already rely on.

**Independent Test**: Send a request with an invalid `group_by` value and confirm a structured RFC 7807
error naming the specific new problem type, distinct from the pre-existing lookback/confidence error
types.

**Acceptance Scenarios**:

```gherkin
Scenario: Invalid group_by value
  Given account "HL-SIPP" exists
  When a client requests GET /v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&lookback=2y&confidence=0.99&group_by=sector
  Then the response returns 422 with problem type "invalid-var-query" and field "group_by"

Scenario: Invalid lookback value reuses the existing problem type
  Given account "HL-SIPP" exists
  When a client requests GET /v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&lookback=3y&confidence=0.99
  Then the response returns 422 with problem type "invalid-var-query" and field "lookback"
```

---

### Edge Cases

- A position with zero or negative market value on the requested date (e.g. a suspended holding) is
  excluded from the contributions breakdown, consistent with how it is excluded from the underlying
  VaR calculation.
- Cash is never excluded this way (FR-018): it always has a positive market value and a defined
  (near-zero) contribution, so it always appears as its own group.
- A theme grouping where every position maps to the same single theme still returns a valid one-row
  response, with that theme's totals equal to the account totals.
- A position whose returns were proxied or rescaled on the requested date still gets a contribution
  figure, carrying the same per-position quality/provenance share already computed for the VaR run,
  so the user can see that a given position's contribution rests on proxied or rescaled data.
- Requesting a date that falls strictly between two computed dates (a gap in the store) is treated the
  same as "not computed" for that date, not an error and not an interpolated value.
- Requesting a `confidence` value not among the account's configured confidence levels for that run is
  rejected the same way an invalid confidence level is rejected by the existing series endpoint.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide `GET /v1/accounts/{account}/risk/var/contributions` accepting query
  parameters `date` (required), `lookback` (optional, defaults to the account's configured headline
  lookback), `confidence` (optional, single value, defaults to the first of the account's configured
  confidence levels — there is no separate "headline confidence" setting, only a headline *lookback*)
  and `group_by` (optional, one of `position` or `theme`, defaults to `position`).
- **FR-002**: For a request whose account/date/lookback/confidence has a completed VaR estimate of
  sufficient quality, the system MUST return one entry per group (position or theme) reporting:
  standalone VaR, incremental VaR, component Expected Shortfall, marginal VaR, market value, weight
  (share of total account market value) and the group's coverage/quality (share actual, proxied,
  rescaled).
- **FR-003**: Component Expected Shortfall values across all groups in a response MUST sum to the
  account's total Expected Shortfall for that date/lookback/confidence, within floating-point rounding
  tolerance.
- **FR-004**: Standalone VaR for a group MUST be computed from that group's own scenario PnL column in
  isolation (the quantile of its own historical scenario returns applied to its own current market
  value), independent of the rest of the portfolio.
- **FR-005**: Incremental VaR for a group MUST be computed as the account's total VaR minus the
  account's total VaR recomputed with that group's exposure removed from the holdings.
- **FR-006**: Marginal VaR for a group MUST be computed as that group's component contribution divided
  by the group's market value, expressing risk per unit of exposure.
- **FR-007**: The system MUST reuse the scenario returns already produced by the most recent successful
  VaR run for the requested account and lookback, without initiating a new calculation run and without
  making any market-data lookups while serving this endpoint.
- **FR-008**: The system MUST persist the aligned scenario-returns snapshot used by a VaR run
  (per instrument, raw and look-back-independent — each look-back's proxy/rescale substitution is
  re-derived from it at read time, not stored separately per look-back) as part of that run's stored
  output, so it remains available for this endpoint after the run completes.
- **FR-009**: When no VaR run has ever produced an estimate for the requested account, date and
  lookback, the system MUST return a 200 response with an empty contributions payload and links to the
  account's VaR status and runs resources, matching the "not computed" shape of the existing VaR series
  endpoint, rather than an error.
- **FR-010**: When the requested date's stored VaR quality is `insufficient` (no VaR value stored), the
  system MUST return a 200 response carrying the same insufficient-quality signal used by the VaR
  series endpoint, with no standalone/incremental/component/marginal values, rather than fabricating
  figures from unreliable data.
- **FR-011**: An invalid `lookback` value MUST be rejected with the existing `invalid-var-query` RFC
  7807 problem type (the same type the series/backtest endpoints already use for this), with
  `fields: ["lookback"]`.
- **FR-012**: An invalid `confidence` value, or one not among the account's configured confidence
  levels, MUST be rejected with the existing `invalid-var-query` RFC 7807 problem type, with
  `fields: ["confidence"]`.
- **FR-013**: An invalid `group_by` value MUST be rejected with the existing `invalid-var-query` RFC
  7807 problem type, with `fields: ["group_by"]` — not a new, separate problem type, consistent with
  how `lookback`/`confidence` are already validated on the neighbouring series/backtest endpoints.
- **FR-014**: Positions with zero or negative market value on the requested date MUST be excluded from
  the contributions breakdown, consistent with their exclusion from the underlying VaR calculation.
- **FR-015**: When grouping `by theme`, the system MUST aggregate market value and all four
  contribution measures across every position mapped to that theme for the requested date.
- **FR-016**: Responses MUST follow the existing HATEOAS (`_links`) and RFC 7807 problem-detail
  conventions used by the other risk endpoints.
- **FR-017**: This feature MUST NOT introduce a what-if / hypothetical-holdings evaluation capability,
  and MUST NOT introduce combined cross-account VaR; both remain explicitly out of scope for a later
  feature.
- **FR-018**: The synthetic Cash position MUST be included in the contributions breakdown as its own
  group — its own row under `group_by=position`, and its own "Cash" theme under `group_by=theme` —
  carrying its market value and weight, with standalone VaR, incremental VaR, component ES and marginal
  VaR all reported as (approximately) zero, since Cash always carries a zero return in the underlying
  VaR calculation.

### Key Entities

- **ContributionGroupEntry**: One row of the response — a position or theme for a given account, date,
  lookback and confidence level. Holds market value, weight, standalone VaR, incremental VaR, component
  ES, marginal VaR, and coverage/quality shares (actual/proxied/rescaled).
- **ScenarioReturnsSnapshot**: The aligned per-instrument historical returns matrix produced by a VaR
  run (raw and look-back-independent), persisted so later contribution requests can be served without
  recomputing scenarios or calling market-data again. Each look-back's proxy/rescale substitution is
  re-derived from this snapshot at request time, not stored separately per look-back.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any account/date/lookback/confidence with a completed, sufficient-quality VaR
  estimate, a contributions request returns a full breakdown (standalone, incremental, component,
  marginal, per group) whose component values sum to the account's total Expected Shortfall within
  0.5% relative tolerance.
- **SC-002**: A contributions request is served without any new market-data network calls and without
  starting a new VaR calculation run, so a request against an already-computed date returns in
  comparable time to the existing VaR series endpoint (sub-second on local data).
- **SC-003**: Requests for a never-computed account/date/lookback, or for a date with insufficient VaR
  quality, always return a 200 response with a clearly distinguishable "nothing to show" or
  "insufficient" shape rather than an error or fabricated figures, in 100% of such cases.
- **SC-004**: Malformed requests (bad lookback, confidence, or grouping) are rejected with a specific,
  distinguishable structured error in 100% of cases, matching the problem type for the specific field
  that was invalid.

## Assumptions

- Feature 012's VaR calculation runs and feature 013's series/backtest endpoints are already in place
  and are the source of the per-position scenario returns, provenance and quality data this feature
  reuses.
- "Theme" grouping uses a `theme` field added by this feature to this service's own identifier
  mapping file (it did not previously exist here — a similarly-named field exists only in the
  separate, legacy standalone script's static JSON, which this service does not read). Populating
  theme values for existing mapping entries is a one-time manual data-entry step, the same way
  `var_proxy` entries were populated for feature 012; an entry with no `theme` set groups under the
  reserved `"Unclassified"` label.
- The persisted scenario-returns snapshot is produced and updated only as a side effect of a VaR
  calculation run (feature 012); this feature only reads it, and does not change when or how runs are
  triggered.
- If the persisted snapshot for an otherwise-computed date/lookback is itself missing (e.g. from a run
  that predates this feature), the system treats that combination as not computed for the purposes of
  this endpoint, the same as FR-009, until a later run produces the snapshot.
- Per-account VaR only; combined ISA+SIPP contributions and what-if/hypothetical evaluations are
  explicitly deferred, per this feature's scope decision.
