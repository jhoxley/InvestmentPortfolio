# Feature Specification: Account Projection Endpoint

**Feature Branch**: `020-projection-endpoint`
**Created**: 2026-09-23
**Status**: Draft
**Input**: User description: "Add a new endpoint GET /v1/accounts/{account_name}/projection to this service. Its contract is already fully specified in the sibling portfolio-browser repo at specs/022-projection-page/contracts/portfolio-analysis-api.md, research.md (#1–#3), and data-model.md — read those first and treat them as the authoritative spec, not a starting point to redesign. In short: reuse PositionTimeSeriesResponse's shape (repurposing position as a series label), compute each requested return's projection as daily_rate = annualized_return * sqrt(260) compounded daily from the start date's market value, and apply aggregate_last_observation() (already in app/services/periodicity_aggregation.py) per series exactly as position_timeseries_service.py already does per position. Reuse the existing performance_metrics.py measures for itd_ann/1y/3y/5y, AccountsService/TimeseriesDateResolver for the start-date default, and follow the existing TimeseriesService/PositionTimeSeriesService layering pattern rather than inventing a new one."

**Note on origin**: This capability was designed and pinned as a downstream dependency by the
`portfolio-browser` repository's own feature 022 ("Projection Page"), specifically
`specs/022-projection-page/contracts/portfolio-analysis-api.md`,
`specs/022-projection-page/research.md` (#1–#3), and `specs/022-projection-page/data-model.md`
in that sibling repository. Those documents are the authoritative source for this endpoint's
wire contract and are treated here as fixed constraints, not open design questions — this spec
translates that already-agreed contract into this service's own requirements and success
criteria, and does not revisit decisions already made there.

## Corrections

### 2026-09-24: Projection formula fixed

The originally pinned formula, `daily_rate = annualized_return * sqrt(260)`, was implemented
exactly as specified and found to be **wrong** — `sqrt(260)` is a volatility-scaling factor, not
a valid way to de-annualize a return. A real account with a 24.2% annualized 3-year return
produced a 390% "daily rate," turning a $33,190 market value into $162,738 the next business
day. The correct de-annualization is the 260th root — `daily_rate = (1 + annualized_return) **
(1/260) - 1` — the exact inverse of how this service's own `performance_metrics.py` annualizes a
return. FR-009 and this section's Gherkin scenario below are updated accordingly; see
`research.md` #5 for the full worked correction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Project an Account's Market Value Forward Using One Return (Priority: P1)

A consumer of the API (a dashboard, a report generator, or any other client) wants to show an
account's actual recorded market-value history followed by a single illustrative projection of
where that value could go, using one of the account's own historical return measures. It
requests the account's projection with a target date and one requested return, and receives back
a single response containing both the historical series up to a start date and a projected
series continuing from that same point to the target date.

**Why this priority**: This is the entire reason the endpoint exists — every other capability
(multiple returns, an implicit start date) builds on a single request/response round trip
working correctly, and it delivers value entirely on its own.

**Independent Test**: For an account with several years of recorded position-ladder history,
request its projection with an explicit `start`, a `projection_date` several years later, and a
single `return`. Verify the response contains one series labeled `"Historical"` spanning the
account's earliest recorded date through `start`, and a second series labeled with that return
spanning `start` through `projection_date`, both reporting `market_value`.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: A single requested return produces one historical and one projected series
  Given an account with a position ladder recorded continuously from 2016-04-20 through 2026-09-22
  When I request the account projection with start "2026-09-22", projection_date "2036-09-22", and return "5y"
  Then the response contains a series labeled "Historical" whose entries span 2016-04-20 through 2026-09-22
  And the response contains a series labeled "5Y" whose entries span 2026-09-22 through 2036-09-22
  And both series report the "market_value" attribute only

Scenario: The projected series begins at the historical series' final recorded value
  Given an account with a position ladder recorded continuously from 2016-04-20 through 2026-09-22
  When I request the account projection with start "2026-09-22", projection_date "2036-09-22", and return "3y"
  Then the "3Y" series' first entry's market_value equals the "Historical" series' final entry's market_value

Scenario: The projected series compounds the requested return's own historical rate
  Given an account whose annualized 3-year return as of 2026-09-22 is a known value r
  And that account's market_value on 2026-09-22 is a known value V0
  When I request the account projection with start "2026-09-22", projection_date "2036-09-22", and return "3y"
  Then each entry's market_value equals V0 compounded daily at rate ((1 + r) ** (1/260) - 1) for the number of business days elapsed since 2026-09-22

Scenario: An explicit projection_date that is not later than the start date is rejected
  Given an account with a position ladder recorded continuously from 2016-04-20 through 2026-09-22
  When I request the account projection with start "2026-09-22", projection_date "2026-09-22", and return "1y"
  Then the request is rejected with a 422 error identifying the invalid date range
```

---

### User Story 2 - Compare Several Returns in a Single Request (Priority: P2)

A consumer wants to show more than one plausible projected path at once — for example, both the
account's 3-year and 5-year historical returns — so a viewer can judge a range of outcomes
without issuing multiple requests. It requests the projection with several `return` values and
receives one projected series per requested return, all in one response, each beginning at the
same historical starting point.

**Why this priority**: This multiplies the value of User Story 1 but is not required for it to
be useful — a single requested return already delivers a complete, useful response. It is next
because it is the most natural extension once the single-return case works.

**Independent Test**: Request the projection for an account with several requested returns at
once. Verify the response contains one series per requested return (each correctly labeled), all
beginning at the same `market_value`, in addition to the one `"Historical"` series.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Multiple requested returns each produce their own series from a shared starting point
  Given an account with a position ladder recorded continuously from 2016-04-20 through 2026-09-22
  When I request the account projection with start "2026-09-22", projection_date "2036-09-22", and returns "3y" and "5y"
  Then the response contains series labeled "Historical", "3Y", and "5Y"
  And the "3Y" and "5Y" series' first entries both equal the "Historical" series' final entry's market_value
  And the "3Y" and "5Y" series' final entries fall on 2036-09-22

Scenario: A requested return without enough recorded history is silently omitted
  Given an account with a position ladder recorded continuously for only two years
  When I request the account projection with a valid start and projection_date, and returns "3y" and "1y"
  Then the response contains the "Historical" series and the "1Y" series
  And the response does not contain a "3Y" series
  And the request succeeds without an error

Scenario: Requesting no returns at all still returns the historical series
  Given an account with a position ladder recorded continuously from 2016-04-20 through 2026-09-22
  When I request the account projection with start "2026-09-22", projection_date "2036-09-22", and no return parameter
  Then the response contains only the "Historical" series
  And the request succeeds without an error
```

---

### User Story 3 - Omit the Start Date to Project From the Account's Latest Record (Priority: P3)

A consumer that always wants "project from today" behavior does not want to look up an account's
latest recorded date itself before every request. It omits `start` entirely, and the service
resolves it to that account's own most recently recorded date automatically, exactly as every
other date-driven endpoint in this service already defaults an omitted start date.

**Why this priority**: This is a convenience that removes one round trip for the most common
case, but every other capability (the projection itself, multiple returns) already works with an
explicit `start`, so this is the least critical piece to deliver.

**Independent Test**: Request the projection for an account, omitting `start`. Verify the
resolved `"Historical"` series' final entry date equals that account's own most recently recorded
position-ladder date, matching what an explicit `start` set to that same date would have
produced.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Omitting start defaults to the account's most recently recorded date
  Given an account whose position ladder's most recently recorded date is 2026-09-22
  When I request the account projection with projection_date "2036-09-22" and return "5y", omitting start
  Then the "Historical" series' final entry's date is 2026-09-22
  And the "5Y" series' first entry's date is 2026-09-22

Scenario: An account with no ingested position ladder cannot be projected
  Given an account with no ingested position ladder
  When I request the account projection for that account
  Then the request is rejected with a 404 error identifying the missing resource
```

---

### Edge Cases

- **A requested `periodicity` bucketing collapses a long combined historical-plus-projected
  span**: the same calendar-aligned aggregation already applied to historical time series
  (feature 008) applies identically across both the historical and every projected series, so a
  twenty-year combined span remains as compact as a twenty-year historical-only request would.
- **An unknown `periodicity` or `return` value**: rejected the same way an unknown value is
  already rejected by the existing time series and performance endpoints — a 422 identifying the
  unsupported value, not a silent fallback.
- **A `return` requested for an account with exactly the minimum but not quite enough history**:
  follows the existing performance-measure convention exactly (a measure with insufficient
  preceding history is simply absent, never zero or null) — omitted, not erroring.
- **`start` explicitly provided later than the account's own most recently recorded date**:
  rejected consistently with how every other date-driven endpoint in this service already
  handles a start date outside a required source's recorded range.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose `GET /v1/accounts/{account_name}/projection`, following the
  same versioned, resource-oriented URL convention as every existing account-scoped endpoint.
- **FR-002**: The system MUST accept an optional `start` date; when omitted, it MUST default to
  the account's own most recently recorded position-ladder date, following the same
  defaulting convention as the existing time series endpoints' date resolution.
- **FR-003**: The system MUST require a `projection_date`, and MUST reject a request whose
  `projection_date` is not strictly later than the resolved `start` date.
- **FR-004**: The system MUST accept an optional `periodicity`, reusing the same supported values
  and default behavior (`day` when omitted) already defined for the existing time series
  endpoints.
- **FR-005**: The system MUST accept zero or more `return` values, each one of the account
  performance measures `itd_ann`, `1y`, `3y`, or `5y` — the same annualized return measures
  already computed for the performance endpoint, excluding its plain, non-annualized `itd`
  measure.
- **FR-006**: The response MUST report a single attribute, `market_value`, using the same
  response structure already used by the existing per-position time series endpoint, with its
  series-discriminator field repurposed to carry a series label rather than a position name.
- **FR-007**: The response MUST always contain exactly one series labeled `"Historical"`,
  covering the account's actual recorded market value from its earliest recorded date through
  the resolved `start` date, at the requested (or defaulted) periodicity.
- **FR-008**: The response MUST contain exactly one additional series per requested return that
  can be computed for the account, each running from the resolved `start` date to
  `projection_date` at the requested (or defaulted) periodicity.
- **FR-009**: Each projected series' values MUST be computed by de-annualizing that return's own
  annualized rate to a daily rate via the 260th root (`(1 + annualized_return) ** (1/260) - 1`,
  the inverse of this service's own annualization convention), then compounding that daily rate
  forward, once per business day, starting from the account's actual `market_value` on the
  resolved `start` date (Corrections, 2026-09-24).
- **FR-010**: Periodicity bucketing MUST be applied to each series (the historical series and
  each projected series) independently, using the same calendar-aligned, last-observation-per-
  window aggregation already used for existing time series responses, applied as an overlay on
  top of the full daily series described in FR-009 — never altering the underlying compounding
  itself.
- **FR-011**: A requested return that cannot be computed for the account (insufficient recorded
  history for that measure) MUST be silently omitted from the response — no series for that
  return, and no error — consistent with how the existing performance endpoint already omits a
  not-yet-computable measure.
- **FR-012**: Requesting zero returns MUST still succeed and MUST return the `"Historical"`
  series alone.
- **FR-013**: An unsupported `periodicity` or `return` value MUST be rejected with the same RFC
  7807 Problem Details error format already used by every other endpoint in this service.
- **FR-014**: A `projection_date` that is not strictly later than the resolved `start` date MUST
  be rejected with the same RFC 7807 Problem Details error format.
- **FR-015**: A request for an account with no ingested position ladder MUST be rejected with the
  same "resource not found" treatment already used by the existing endpoints that require a
  position ladder.
- **FR-016**: The response MUST include HATEOAS navigation links, following the same `_links`
  convention already used by every other endpoint in this service.

### Key Entities *(include if feature involves data)*

- **Projection Request**: An account, a start date (defaulting to that account's most recently
  recorded date), a projection target date, a periodicity, and zero or more requested returns.
- **Historical Series**: The account's actual recorded market value from its earliest recorded
  date through the request's resolved start date, at the requested periodicity. Exactly one per
  request, independent of which returns were requested.
- **Projected Series**: One per requested-and-computable return. A sequence of projected
  market-value points beginning at the start date's actual market value and running to the
  projection target date, at the requested periodicity, each point reflecting the compounding
  effect (FR-009) of that return's own historical rate applied since the start date.
- **Return**: One of the account's existing annualized performance measures — `itd_ann`, `1y`,
  `3y`, or `5y` — reused unmodified from the performance capability, not recalculated or
  redefined for this endpoint.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consumer can retrieve an account's full recorded history plus a projection
  running any number of years into the future, for any number of supported returns, in a single
  request.
- **SC-002**: A twenty-year combined historical-plus-projected span, requested at a coarse
  periodicity, returns a number of data points consistent with the existing time series
  endpoints' own reduction at that same periodicity (e.g. roughly one point per year at annual
  periodicity), not one point per business day.
- **SC-003**: Requesting a return the account does not yet have enough history for never causes
  the overall request to fail — the response always contains the historical series plus every
  other valid requested return.
- **SC-004**: Every projected value in a response is exactly reproducible from the account's own
  recorded market value and its own historical return measures — no randomness, no external
  inputs beyond the account's own recorded data.
- **SC-005**: An invalid request (a non-future `projection_date`, an unsupported `periodicity` or
  `return`, or an account with no position ladder) is always rejected with a clear, structured
  error rather than a partial or malformed response.

## Assumptions

- This endpoint's wire contract (query parameters, response shape, and the projection formula)
  was already fully designed and agreed as a downstream dependency of `portfolio-browser`'s
  feature 022, and is treated here as fixed — this spec does not reconsider it.
- The response reuses the existing per-position time series response shape exactly, with its
  series-discriminator field carrying a series label instead of a position name; no new response
  model is introduced.
- The compounding formula (`daily_rate = (1 + annualized_return) ** (1/260) - 1`, FR-009) is a
  deliberate, simple, transparent illustrative projection, not a statistically rigorous
  forecast — but it must still be arithmetically correct de-annualization, which the originally
  pinned `sqrt(260)` formula was not (Corrections, 2026-09-24).
- Periodicity bucketing is achieved by reusing the existing aggregation capability already used
  by the other time series endpoints, applied once per series, with no new aggregation logic.
- The four supported returns are computed by reusing the existing account performance
  calculation exactly as already computed for the performance endpoint; no new return
  calculation is introduced.
- The endpoint's start-date defaulting reuses the same account/date resolution pattern already
  used by the existing time series endpoints.
- No new authentication, authorization, or rate-limiting behavior is introduced beyond what every
  other endpoint in this service already has.
- The currently known consumer of this endpoint is `portfolio-browser`'s Projection page, but
  nothing in this endpoint's contract is specific to that one consumer.
