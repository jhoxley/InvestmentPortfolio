# Feature Specification: On-Demand Ladder Rebuild for Stale Requests

**Feature Branch**: `014-ladder-rebuild-stale`
**Created**: 2026-11-10
**Status**: Draft
**Input**: User description: "there is a behavior in this service around forward-filling the last ingested ladder that needs to be changed. The current problem today is that executing /v1/accounts/HL-ISA/timeseries?attribute=market_value&start=2026-07-01&end=2026-11-06&periodicity=day returns flat-filled data from 2026-09-23 through to 2026-11-06 despite there being available market data for the missing ~40 days. Adjust all the 'GET' endpoints that read from the ladder and capital ladder ingested by this service to trigger a rebuild of missing data if the requested date is after the last ingestion date. This new date must be capped at the prior business date to today and not attempt to seek market data into the future. When the data is populated it should be stored down for subsequent requests so that only a single rebuild for the missing period is requested. For this feature it is reasonable to assume that the last known portfolio positions continue forward and are only adjusted by more recent pricing market data. Ensure the ingestion path continues to work with this behaviour. For example in the above example fresh market data projects the 2026-09-23 positions forward to 2026-11-06 but if at a later date a new ledger is ingested for 2026-11-01 that contains corporate actions or trades for the October time period the persisted ladder must be correctly rebuilt to now include that information."

## Clarifications

### Session 2026-11-10

- Q: Should the rebuild run synchronously inside the triggering GET request, asynchronously in the background, or synchronously-with-timeout-fallback? → A: Synchronous — the triggering GET request blocks until the rebuild completes, then returns fresh data.
- Q: If market pricing is unavailable for the *entire* missing gap (e.g., the market-data dependency is down), what should the triggering request do? → A: Fall back silently to the old flat-filled data for this request; retry the rebuild on the next request. Nothing is persisted from the failed attempt.
- Q: For dates within the gap where pricing is unavailable (partial-unavailability case), how should those specific dates appear in the response? → A: Included with a null/absent value; dates where pricing resumes are rebuilt normally rather than flat-filled.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh market data instead of stale flat-fill (Priority: P1)

An analyst requests a timeseries, position, or performance view for an account whose underlying ladder was last ingested or rebuilt weeks ago. Instead of receiving the last known value repeated flat across every day since, the analyst receives values that reflect real, day-by-day market pricing for every business day up to the most recently completed business day, with portfolio holdings held at their last known quantities.

**Why this priority**: This is the core defect being fixed — stale flat-filled figures are misleading for any analysis (performance, risk, valuation) that spans a period where the account has gone unrefreshed. Without this, every other story is moot.

**Independent Test**: Can be fully tested by requesting a date range that extends past an account's last ingested/rebuilt date and confirming the returned values vary day-to-day in line with market pricing, rather than repeating the last stored value.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Timeseries request extends past the last ingested date
  Given an account's ladder was last ingested or rebuilt through 2026-09-23
  And market pricing is available for business days between 2026-09-23 and 2026-11-06
  When a GET timeseries request is made for market_value from 2026-07-01 to 2026-11-06
  Then the response contains day-by-day values for 2026-09-24 through 2026-11-06 that vary with market pricing
  And no two consecutive business days in that range have an identical flat-filled value unless market pricing was genuinely unchanged

Scenario: Requested end date is in the future
  Given today's date is 2026-11-10 and the prior business day is 2026-11-09
  When a GET timeseries request is made with end=2026-11-12
  Then the system does not attempt to source or project market data beyond 2026-11-09
  And data for 2026-11-10 through 2026-11-12 is not fabricated
```

---

### User Story 2 - Rebuild happens once, not on every request (Priority: P2)

After the first request triggers a rebuild of the missing period, subsequent requests covering the same (or a narrower) gap are served directly from the newly persisted data, without re-running the rebuild.

**Why this priority**: Without this, every stale request would re-trigger a costly rebuild, degrading performance and risking duplicate or conflicting market-data calls. This is what makes the fix production-safe.

**Independent Test**: Can be fully tested by issuing the same stale request twice and confirming that the data-sourcing/rebuild work only occurs on the first call, with the second call served from storage.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Second request after rebuild does not re-trigger sourcing
  Given a prior request already rebuilt an account's ladder through 2026-11-09
  When a second GET request is made for a range within or before 2026-11-09
  Then the response is served from persisted data
  And no new market-data sourcing work is performed

Scenario: Concurrent requests for the same gap produce one rebuild
  Given an account's ladder is stale and two GET requests for overlapping ranges arrive at the same time
  When both requests require the same missing period to be rebuilt
  Then only one rebuild of that missing period is performed
  And both requests return consistent, correctly rebuilt data
```

---

### User Story 3 - Later ledger ingestion corrects previously rebuilt periods (Priority: P3)

Some time after a gap has been rebuilt using projected positions and fresh pricing, the account owner ingests a new ledger that includes trades or corporate actions dated within that previously-rebuilt period. The persisted ladder is corrected so that the affected period now reflects the real trades/corporate actions, not the earlier position-held-constant projection.

**Why this priority**: This preserves correctness of the ingestion path and prevents the rebuild feature from permanently "baking in" an incorrect projection once real transaction history becomes available. It matters less often than Stories 1 and 2 but is essential to avoid silent, lasting data corruption.

**Independent Test**: Can be fully tested by rebuilding a gap, then ingesting a ledger with a transaction dated inside that gap, and confirming the persisted ladder for that period changes to reflect the new transaction.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: New ledger supersedes a previously rebuilt period
  Given an account's ladder was rebuilt from 2026-09-23 through 2026-11-06 using held-constant positions
  When a new ledger is ingested on 2026-11-01 containing a trade dated 2026-10-15
  Then the persisted ladder for the period from 2026-10-15 forward is recomputed to include that trade
  And the previously rebuilt figures that assumed held-constant positions across that date are replaced
```

---

### Edge Cases

- What happens when the requested end date is before or equal to the last ingested/rebuilt date? No rebuild should occur; existing read behavior is unchanged.
- What happens when market pricing is unavailable for part of the gap (e.g., a holding's pricing source has a temporary outage)? The system persists as much of the rebuild as it can source, represents the unsourced dates with a null/absent value, and rebuilds normally once pricing resumes for later dates in the same gap.
- What happens when market pricing is unavailable for the entire gap (e.g., the market-data dependency is down)? The triggering request falls back to returning the prior flat-filled data for that request only; nothing is persisted from the failed attempt, and the next request retries the rebuild.
- What happens when an account has never been ingested at all? There is no ladder to extend; existing "account not found / no data" behavior applies, and no rebuild is attempted.
- What happens when the prior business day itself has no new market data yet (e.g., a request made very early in the day)? The rebuild target is still capped at the prior business day; the system does not wait for or substitute same-day/future data.
- What happens when a rebuild is triggered for the ladder but the capital ladder is already current (or vice versa)? Each is evaluated and rebuilt independently based on its own last-ingested-or-rebuilt date.
- What happens when a newly ingested ledger's transactions fall entirely outside any previously rebuilt range? No supersession is needed; ingestion proceeds as it does today.
- What happens when a rebuild is still in progress and a request for an overlapping but larger range arrives? The system must not return partially-written or inconsistent data, and must not start a second, redundant rebuild of the same already-in-progress period.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every GET endpoint that reads a per-account position ladder or capital ladder bounded by a requested date range (including, but not limited to, account timeseries, position timeseries, performance, and risk return-histogram) MUST compare the resolved request end date against the last ingested-or-rebuilt date of the relevant ladder before composing its response.
- **FR-002**: When the resolved request end date falls after the last ingested-or-rebuilt date, the system MUST rebuild the missing period by carrying forward the last known position quantities and applying newly retrieved market pricing for each missing business day.
- **FR-003**: The rebuild's target end date MUST be capped at the prior business day relative to the date the request is made, and the system MUST NOT attempt to retrieve or project market data for the current day or any future date.
- **FR-004**: Rebuilt data MUST be persisted so that subsequent GET requests covering the same or an earlier range are served without repeating the rebuild.
- **FR-005**: When multiple requests concurrently require a rebuild of the same missing period for the same account, the system MUST ensure only one rebuild of that period is performed and that all concurrent requesters receive consistent results.
- **FR-006**: The capital ladder MUST be subject to the same rebuild-on-stale-request, cap-at-prior-business-day, and persist-once behavior as the position ladder, evaluated independently per ladder.
- **FR-007**: The ledger ingestion path MUST continue to function unchanged for its existing responsibilities (validating, expanding, pricing, and persisting newly ingested ledgers) in addition to supporting the new rebuild behavior.
- **FR-008**: When a newly ingested ledger contains trades or corporate actions dated within a period that was previously populated by a rebuild (i.e., projected from held-constant positions), the system MUST recompute the persisted ladder for the affected period so it reflects the newly ingested transactions rather than the earlier projection.
- **FR-009**: The system MUST be able to distinguish, for any previously persisted date, whether that date's data originated from directly ingested ledger transactions or from a rebuild projection, so that FR-008 can be correctly applied when new ledger data arrives.
- **FR-010**: If market pricing needed to complete a rebuild is unavailable for part of the requested gap, the system MUST persist the portion of the rebuild it could complete, MUST represent each unsourced date with a null/absent value rather than a fabricated or flat-filled figure, and MUST rebuild normally (not flat-fill) any later date within the gap for which pricing resumes.
- **FR-011**: GET endpoints that do not accept a date range (e.g., ladder metadata summaries, raw ladder downloads, account listings) are not required to independently trigger a rebuild, but MUST reflect the most recently persisted state, including any rebuild triggered via another endpoint.
- **FR-012**: A triggering GET request MUST block until the rebuild of its required missing period completes, and MUST return the freshly rebuilt data in its response rather than the stale flat-filled data that preceded the rebuild.
- **FR-013**: If market pricing needed for a rebuild is entirely unavailable, the triggering request MUST fall back to returning the existing flat-filled data for that request only, MUST NOT persist any partial or failed rebuild state, and MUST allow a subsequent request to retry the rebuild.

### Key Entities *(include if feature involves data)*

- **Position Ladder**: The persisted, per-account time series of position holdings and valuations. Gains a notion of "last ingested-or-rebuilt date" and, per date, whether that date's values came from an ingested ledger or from a rebuild projection.
- **Capital Ladder**: The persisted, per-account time series of capital/cash movements and balances. Carries the same last-ingested-or-rebuilt and provenance concepts as the Position Ladder, tracked independently.
- **Rebuild Coverage**: The record of which date ranges in a ladder were populated by projection (held-constant positions plus fresh pricing) versus by direct ledger ingestion. Used to detect when newly ingested ledger data must supersede a previously projected range.
- **Market Pricing Data**: Externally sourced valuation data used to price held-constant positions forward during a rebuild.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an account whose ladder is stale by a multi-week gap, a single GET request returns values for every missing business day that vary in line with real market pricing rather than repeating one flat-filled figure.
- **SC-002**: After an initial request triggers a rebuild, a repeat request for the same or a narrower range completes without re-performing the data-sourcing work, and returns identical results to the first rebuilt response.
- **SC-003**: No GET response, under any requested date range, ever contains position or capital data for a date later than the prior business day relative to when the request was made.
- **SC-004**: When a ledger is ingested that includes transactions dated within a previously rebuilt period, a subsequent read of that period reflects the newly ingested transactions, with no manual data correction required.
- **SC-005**: Concurrent requests that each require the same missing period to be rebuilt result in exactly one rebuild of that period, with no duplicated work and no inconsistent results returned to different requesters.

## Assumptions

- Last known portfolio position quantities are held constant across a rebuilt/projected period; only market pricing is treated as new information during a rebuild, consistent with the feature request.
- "Prior business day" uses the same business-day definition (Monday–Friday, no holiday calendar) already applied elsewhere in this service's date handling.
- The "single rebuild" guarantee in FR-005 applies to concurrent requests racing for the same gap; since the rebuild is synchronous (FR-012), any requester arriving while a rebuild is already in flight waits for that same in-progress rebuild rather than starting a new one.
- GET endpoints without a date-range parameter (ladder metadata summary, raw ladder download, account listing) do not themselves evaluate staleness or trigger a rebuild, since they have no requested end date to compare; they simply read whatever is currently persisted.
- A rebuild applies independently to the position ladder and the capital ladder for a given account; one may be rebuilt without the other if only one is stale.
- This feature does not change how an account becomes stale in the first place (e.g., cadence of ledger re-ingestion) — it only changes how read requests behave when staleness exists.
