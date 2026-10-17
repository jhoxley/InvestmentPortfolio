# Feature Specification: Account Performance Retrieval Endpoints

**Feature Branch**: `007-performance-endpoints`
**Created**: 2026-07-26
**Status**: Draft
**Input**: User description: "Create a new group of API endpoints for 'performance' data retrieval. The initial version should follow similar pattern to /v1/accounts/{account_name}/timeseries and /v1/timeseries/attributes. One endpoint to return the data in a shape suitable for charting in a Dash App and the other endpoint providing metadata on what measures and attributes are available. For the analytic data, the arguments should be the same as for /v1/accounts/{account_name}/timeseries and the response payload should be the same. The new endpoint is primarily concerned with exposing returns attributes and in the first iteration will expose \"ITD\" (Inception to Date), \"ITD (Ann.)\" (Inception to Date, annualized), \"1Y\" (cumulative product of last 260 trading days), \"3Y\" (cumulative product of last 780 trading days, scaled by power of 1/3rd to annualize), \"5Y\" (cumulative product of last 1300 trading days, scaled by power of 1/5th to annualize). To get a daily portfolio return sum the 'weighted_position_return' across all positions on that date. When considering the requested start/end date of the GET request the computation of underlying analytics should always look back as far as needed to return a value for the requested date. For example, A 3Y return for 1st Jan 2022 should still look-back to underlying data from 1st Jan 2019 onwards despite only showing the requested window in results. If this look-back would go past the earliest record in the account then no result can be produced - the 3Y and 5Y returns only start populating 3 or 5 years from the first date of the chosen account."

## Clarifications

### Session 2026-07-26

- Q: For a requested performance measure that can't yet be computed on a given date (e.g. a 5Y
  return requested for a date less than 5 years after the account's first record), how should
  that date's entry represent it? → A: The entry for that date is still returned (other requested
  measures still populate normally), but the key for the not-yet-computable measure is simply
  omitted from that entry — mirroring how the existing time series endpoint already omits keys
  for attributes that weren't requested at all.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily Portfolio Return Feeds Every Performance Measure (Priority: P1)

A developer building a performance chart needs a single daily figure that represents the whole
account's return for a business day, derived from the account's already-computed per-position
weighted daily returns, so that every other performance measure (ITD, annualized ITD, 1Y, 3Y, 5Y)
can be built from one consistent daily series instead of each re-deriving it differently.

**Why this priority**: Every other measure in this feature is a rollup of the same daily
portfolio return; if that figure isn't computed correctly and consistently, every derived measure
is wrong too.

**Independent Test**: For an account with two or more positions active on the same business day,
verify the account's daily portfolio return for that day equals the sum of `weighted_position_return`
across every position present in that day's position ladder.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Daily portfolio return is the sum of weighted position returns
  Given a position ladder for account "test-portfolio" with sub-accounts "Equities A" and
      "Equities B" both present on 2024-03-04
  And on 2024-03-04, "Equities A" has weighted_position_return 0.011 and "Equities B" has
      weighted_position_return -0.0045
  When the account's daily portfolio return for 2024-03-04 is computed
  Then it equals 0.011 + (-0.0045), i.e. 0.0065
```

---

### User Story 2 - Retrieve Charting-Ready Performance Measures for an Account (Priority: P1)

A developer building a Dash App chart requests one or more performance measures — Inception to
Date return, annualized Inception to Date return, 1-year, 3-year, and 5-year trailing returns —
for an account over a date range, using the same request shape (account in the path, repeated
`attribute` parameter, optional `start`/`end`) already used for the existing account time series
endpoint, and gets back a response in the same shape: one entry per business day carrying that
day's value for each requested measure.

**Why this priority**: This is the primary deliverable of the feature — without it, performance
measures exist only as an internal computation with no way for a caller to retrieve them.

**Independent Test**: Request `ITD` and `1Y` for an account with more than a year of ingested
history over an explicit date range, and verify the response returns one entry per business day
in the resolved range, each carrying a numeric `ITD` value and (where at least a year of prior
history exists) a numeric `1Y` value, using the same field names (`account_name`, `attributes`,
`from_date`, `to_date`, `entries`, `_links`) as the existing time series response.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Requesting performance measures returns a timeseries-shaped response
  Given account "test-portfolio" has an ingested position ladder spanning 2020-01-02 through
      2025-06-02 with a daily portfolio return computed for every business day
  When a request is made for
      "/v1/accounts/test-portfolio/performance?attribute=ITD&attribute=1Y&start=2025-01-02&end=2025-01-10"
  Then the response has an "account_name" of "test-portfolio", an "attributes" list of
      ["ITD", "1Y"], a "from_date" of 2025-01-02, a "to_date" of 2025-01-10, and one entry per
      business day in that range, each with a numeric "ITD" value and a numeric "1Y" value
  And the response includes "_links" navigation entries, consistent with the existing time
      series endpoint

Scenario: Same request arguments and defaults as the existing timeseries endpoint
  Given account "test-portfolio" has an ingested position ladder
  When a request is made for "/v1/accounts/test-portfolio/performance?attribute=ITD" with no
      "start" or "end" supplied
  Then the resolved date range defaults the same way the existing
      "/v1/accounts/test-portfolio/timeseries" endpoint would: start defaults to the earliest
      date the underlying data supports and end defaults to the business day before today
```

---

### User Story 3 - Trailing and Annualized Returns Look Back Beyond the Requested Window (Priority: P1)

A developer requests a 3-year or 5-year trailing return for a date near the start of their
requested window, and the system correctly reaches back into daily returns recorded before that
window — not just the data inside the requested `start`/`end` — so the returned figure reflects
the full trailing period, even though only the requested window's dates appear in the response.

**Why this priority**: Without look-back beyond the requested window, trailing measures would be
silently wrong (too short a window, or blended with pre-window and in-window data incorrectly)
whenever a caller requests a narrow date range, which is expected to be the common case for a
chart showing "the last 6 months" of an otherwise multi-year performance history.

**Independent Test**: Request a `3Y` value for a single date, where the account has at least 3
years of daily portfolio returns recorded strictly before that date but the request's `start` is
the same as the requested date (i.e. no in-window history at all). Verify the returned `3Y` value
still reflects the full trailing 3-year window ending on that date.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: 3Y return for a narrow window still uses the full trailing history
  Given account "test-portfolio" has daily portfolio returns recorded continuously from
      2019-01-01 through 2022-01-01 and beyond
  When a request is made for
      "/v1/accounts/test-portfolio/performance?attribute=3Y&start=2022-01-01&end=2022-01-01"
  Then the single returned entry's "3Y" value is computed from the cumulative product of daily
      portfolio returns for the trailing 780 trading days ending 2022-01-01 (reaching back to
      on or around 2019-01-01), not merely from data within the requested window

Scenario: Trailing return has no value before enough history exists
  Given account "test-portfolio" has its first recorded daily portfolio return on 2021-06-01
  When a request is made for
      "/v1/accounts/test-portfolio/performance?attribute=3Y&start=2021-06-01&end=2021-06-01"
  Then the entry for 2021-06-01 has no "3Y" key, because a full 780-trading-day trailing window
      ending on that date would reach back before the account's first recorded date
```

---

### User Story 4 - Discover Available Performance Measures (Priority: P2)

A developer integrating with the performance endpoints first calls a metadata endpoint to learn
which measures are supported, what each one means, and what underlying data each is derived from
— the same discovery workflow already available for the existing time series attribute metadata
endpoint.

**Why this priority**: Callers need to know what's available and how each figure is derived
before they can request it meaningfully or explain it to end users of a chart; this is lower
priority than the measures themselves since a first integration can hard-code the five known
measure names before wiring up discovery.

**Independent Test**: Call the performance metadata endpoint and verify it lists an entry for
each of "ITD", "ITD (Ann.)", "1Y", "3Y", and "5Y", each with a human-readable description and a
named source.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Performance attribute metadata lists all five measures
  When a request is made for "/v1/performance/attributes"
  Then the response includes exactly five attribute entries named "ITD", "ITD (Ann.)", "1Y",
      "3Y", and "5Y", each with a non-empty description and a source
```

---

### Edge Cases

- What happens when a requested measure's trailing (or, for ITD, full-history) look-back window
  would reach earlier than the account's first recorded daily portfolio return? → That measure is
  simply not included on the affected date's entry (its key is omitted); other requested measures
  that don't need as much history continue to populate normally on that same entry, per the
  Clarifications above.
- What happens on the account's very first recorded date? → `ITD` and `ITD (Ann.)` are defined
  (a single day of zero portfolio return produces `ITD` = 0.0 and `ITD (Ann.)` = 0.0); `1Y`, `3Y`,
  and `5Y` are not yet available, since their full trailing windows cannot be satisfied.
- What happens when the account has no position ladder ingested at all? → The request fails the
  same way the existing time series endpoint fails when a required source is missing for an
  account with no ingested resources at all (404/422, consistent with existing behaviour), since
  every performance measure depends entirely on daily portfolio returns derived from the position
  ladder.
- What happens when `start`/`end` are omitted? → They default the same way as the existing
  `/v1/accounts/{account_name}/timeseries` endpoint: `end` defaults to the business day before
  today, `start` defaults to the earliest date the underlying data supports.
- What happens when no `attribute` is supplied, or an unsupported attribute name is supplied? →
  The request is rejected, consistent with the existing time series endpoint's handling of the
  same conditions.
- What happens when a sub-account's daily returns include a data gap (a divestment followed by a
  later re-entry, per feature 006)? → No special handling is needed here: the daily portfolio
  return for any given date is simply the sum of that date's `weighted_position_return` values
  across whichever positions are present in that day's ladder row set, which already accounts for
  gaps at the position level.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute a daily portfolio return for each business day of an
  account's position ladder, equal to the sum of `weighted_position_return` across every position
  present in that day's ladder rows.
- **FR-002**: The system MUST expose a new endpoint, `GET /v1/accounts/{account_name}/performance`,
  accepting the same request arguments as the existing `GET /v1/accounts/{account_name}/timeseries`
  endpoint: the account name as a path parameter, one or more repeated `attribute` query
  parameters (at least one required), and optional `start`/`end` query parameters.
- **FR-003**: `GET /v1/accounts/{account_name}/performance` MUST return a response body in the
  same structure as the existing time series endpoint's response: the account identifier, the
  list of requested attributes in request order, the resolved start and end dates, one entry per
  business day in the resolved range (each entry carrying that day's value for every requested,
  computable measure), and navigation links.
- **FR-004**: `start`/`end` defaulting and business-day resolution for the performance endpoint
  MUST follow the same rules as the existing time series endpoint (default `end` to the business
  day before today; default `start` to the earliest date the underlying data supports; reject a
  future `end`; reject a resolved start later than the resolved end).
- **FR-005**: The system MUST support the following performance measures as valid values of the
  `attribute` parameter: `ITD`, `ITD (Ann.)`, `1Y`, `3Y`, and `5Y`.
- **FR-006**: `ITD` for a given date MUST equal the cumulative product of `(1 + daily portfolio
  return)` across every business day from the account's first recorded daily portfolio return
  through that date, minus 1.
- **FR-007**: `ITD (Ann.)` for a given date MUST equal `ITD` (per FR-006) annualized using the
  same power-scaling approach as the `3Y`/`5Y` measures (FR-009): the number of elapsed trading
  days is the count of business days from the account's first recorded daily portfolio return
  through that date, and annualization uses a 260-trading-day year, consistent with this
  project's existing trading-day-per-year convention.
- **FR-008**: `1Y` for a given date MUST equal the cumulative product of `(1 + daily portfolio
  return)` across the trailing 260 business days ending on that date, minus 1, with no additional
  annualization scaling.
- **FR-009**: `3Y` and `5Y` for a given date MUST each equal the cumulative product of
  `(1 + daily portfolio return)` across the trailing 780 (for `3Y`) or 1300 (for `5Y`) business
  days ending on that date, then annualized by raising `(1 + cumulative product − 1)` to the
  power of `1/3` (for `3Y`) or `1/5` (for `5Y`), minus 1.
- **FR-010**: For every requested measure, the look-back window used to compute that measure's
  value on a given date MUST extend as far before the requested `start` date as the measure's
  definition requires (FR-006 through FR-009), regardless of the requested `start`/`end` window;
  only dates within the resolved `start`/`end` window appear in the response.
- **FR-011**: When a requested measure's look-back window for a given date would need daily
  portfolio return data earlier than the account's first recorded daily portfolio return, the
  system MUST omit that measure's key from that date's entry rather than producing an
  error or a placeholder value, while still populating the entry with any other requested
  measure that can be computed for that date.
- **FR-012**: The system MUST expose a new endpoint, `GET /v1/performance/attributes`, that
  describes every measure supported by FR-005, each with a human-readable description and the
  data it's derived from — mirroring the existing `GET /v1/timeseries/attributes` endpoint.
- **FR-013**: `GET /v1/accounts/{account_name}/performance` MUST fail using the same account/
  missing-source error handling as the existing time series endpoint when the account has no
  ingested position ladder at all (no daily portfolio return can be computed).
- **FR-014**: `GET /v1/accounts/{account_name}/performance` MUST reject requests with no
  `attribute` supplied, or with an unsupported attribute name, consistent with the existing time
  series endpoint's validation behaviour.

### Key Entities

- **Daily Portfolio Return**: A per-business-day, account-level fraction equal to the sum of
  `weighted_position_return` across every position present in that day's position ladder; the
  single input every performance measure below is derived from.
- **ITD (Inception to Date)**: The cumulative return of an account's Daily Portfolio Return from
  the account's first recorded date through a given date.
- **ITD (Ann.) (Inception to Date, Annualized)**: The ITD figure expressed as an annualized rate,
  scaled by the number of trading days elapsed since inception.
- **1Y / 3Y / 5Y (Trailing Return)**: The cumulative return of an account's Daily Portfolio Return
  over the trailing 260, 780, or 1300 business days ending on a given date; `3Y` and `5Y` are
  additionally annualized by the corresponding root (1/3 or 1/5), `1Y` is not annualized.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller can retrieve any of the five performance measures for an account using the
  same request shape (path, query parameters, defaulting behaviour) as the existing account time
  series endpoint, with no additional arguments to learn.
- **SC-002**: For an account with more than 5 years of continuous ingested history, requesting all
  five measures for a single recent date returns a numeric value for every one of them.
- **SC-003**: For an account with between 1 and 3 years of ingested history, requesting all five
  measures for the account's most recent date returns numeric `ITD`, `ITD (Ann.)`, and `1Y`
  values, and omits `3Y` and `5Y` from that entry.
- **SC-004**: A trailing measure (`1Y`, `3Y`, or `5Y`) requested for a narrow date window (for
  example, a single day) produces the same value as requesting it as part of a wider window that
  includes that same day — confirming the look-back is independent of the requested window size.
- **SC-005**: A caller can discover all five supported measures, each with a description and
  source, via a single metadata request, without needing to consult documentation outside the
  API.

## Assumptions

- The daily portfolio return (FR-001) is computed at request time from each position's already
  persisted `weighted_position_return` (feature 006); this feature does not introduce a new
  ingestion-time persistence step of its own, since the underlying per-position figures are
  already stored.
- `ITD`, `ITD (Ann.)`, `1Y`, `3Y`, and `5Y` are exposed using exactly those literal strings as the
  `attribute` query parameter values and response entry keys, matching the names given in the
  feature description; this differs from the snake_case naming convention used by the existing
  time series attributes, since these names were explicitly specified as the desired user-facing
  labels.
- The "earliest record" boundary referred to for look-back purposes (FR-011) is the account's
  earliest position ladder date, since every performance measure in this feature derives solely
  from `weighted_position_return`, which is only present in the position ladder.
- The new performance endpoints operate at the whole-account level only (no per-position
  filtering), matching the existing `/v1/accounts/{account_name}/timeseries` endpoint's scope
  rather than the position-level timeseries endpoint's.
- The `/v1/performance/attributes` metadata endpoint describes only the five measures in this
  feature's scope; it is a separate endpoint from `/v1/timeseries/attributes` and does not merge
  the two lists.
- A "trading day" / "business day" in this feature means the same business-day date series
  (`freq='B'`) already used throughout the existing position ladder and time series features.
- No minimum-history floor is applied to `ITD (Ann.)` beyond what FR-007's formula naturally
  produces; annualizing a very short elapsed period (e.g. a handful of days since inception) can
  produce a large-magnitude figure, consistent with standard performance-reporting practice for
  young accounts.
