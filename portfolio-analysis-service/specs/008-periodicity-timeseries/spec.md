# Feature Specification: Periodicity Parameter for Account & Position Time Series

**Feature Branch**: `008-periodicity-timeseries`
**Created**: 2026-09-22
**Status**: Draft
**Input**: User description: "Add an additional parameter to two endpoints to support periodicity: /v1/accounts/{account_name}/timeseries, /v1/accounts/{account_name}/position - both should behave the same and the periodicity field should support common time frames: day, week, month, quarter, annual. The 'day' periodicity is default if none specified (this param is optional) and the two endpoints would behave exactly as they do now. If periodicity is explicitly provided and is another interval, then the start/end date range should be divided up into units matching the periodicity (e.g. 'annual' for 2016-2026 gives 10 windows; 'month' for the same would give 120 windows). These windows should be aligned to real calendar, not the provided dates (e.g. 'annual' is from 01-Jan, 'week' is from every Monday, 'month' is from the 1st of each calendar month). The output payload should have an optional field indicating which periodicity was selected but this needs to be backward compatible for existing clients. The start date for each interval is the date in the response payload and the analytic attribute would be the LAST observation of that attribute in the current interval."

## Clarifications

### Session 2026-09-22

- Q: When the resolved start date falls mid-period (e.g. a range starting 2016-03-15 requested
  at annual periodicity), what date should the first window's entry report — the calendar
  boundary (2016-01-01), the resolved start date (2016-03-15), or should the partial window be
  dropped? → A: Clamp to the resolved start date. The partial first window is always emitted,
  dated at the resolved start, so no entry date ever falls outside the response's stated
  from/to range. Every subsequent window is dated at its own calendar boundary.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coarser Account Time Series for Long Date Ranges (Priority: P1)

A consumer of the account time series needs to display or analyse a decade of account history
(e.g. capital, market value, PnL) without handling thousands of daily observations. They repeat
their existing request, adding a single periodicity choice (week, month, quarter or annual), and
receive one observation per calendar period instead of one per business day. Each returned
observation carries the date of the period it represents and the attribute values as they stood
at the end of that period, so long-range trends are immediately usable for charting and
reporting.

**Why this priority**: This is the core value of the feature — reducing a multi-year daily
series to a period-level series is what makes long-horizon analysis and charting practical. It
delivers value on its own, before the position endpoint is touched.

**Independent Test**: Request the account time series for an account with at least two full
calendar years of ingested data, once with no periodicity and once with annual periodicity.
Verify the annual response contains exactly one entry per calendar year covered by the resolved
range, and that each entry's attribute values equal the values in the daily response on the
last business day of the corresponding calendar year (or the resolved end date, for the final,
partial year).

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Annual periodicity collapses a multi-year daily series into one entry per calendar year
  Given an account with capital ingested continuously from 2016-01-04 through 2025-12-31
  When I request the account time series for attribute "capital" from 2016-01-04 to 2025-12-31 with periodicity "annual"
  Then the response contains exactly 10 entries
  And the entries' dates are the first business day on or after 01 January of 2016 through 2025, in ascending order
  And each entry's "capital" value equals the daily series value on the last business day of that calendar year

Scenario: Monthly periodicity divides the same range into calendar months
  Given an account with capital ingested continuously from 2016-01-04 through 2025-12-31
  When I request the account time series for attribute "capital" from 2016-01-04 to 2025-12-31 with periodicity "month"
  Then the response contains exactly 120 entries
  And each entry's date is the first business day on or after the 1st of its calendar month

Scenario: Weekly periodicity aligns to calendar weeks beginning on Monday
  Given an account with capital ingested continuously from 2026-01-05 through 2026-02-27
  When I request the account time series for attribute "capital" from 2026-01-05 to 2026-02-27 with periodicity "week"
  Then every entry's date falls on a Monday, or on the first business day of that week when its Monday is a non-business day
  And each entry's "capital" value equals the daily series value on the last business day of that calendar week

Scenario: Aggregated entries carry the last observation of every requested attribute
  Given an account with capital and market value ingested continuously across January and February 2026
  When I request the account time series for attributes "capital" and "market_value" for January and February 2026 with periodicity "month"
  Then each entry carries both "capital" and "market_value"
  And both values on each entry are taken from the same date — the last business day of that entry's month within the resolved range

Scenario: Omitting periodicity preserves today's per-business-day behaviour
  Given an account with capital ingested continuously across January 2026
  When I request the account time series for attribute "capital" across January 2026 with no periodicity parameter
  Then the response contains one entry per business day in the resolved range
  And the response body is unchanged from the response produced before this feature existed, apart from the added periodicity field
```

---

### User Story 2 - Coarser Position Time Series for Long Date Ranges (Priority: P2)

A consumer of the per-position time series needs the same period-level view across a long
horizon — for example each position's market value at every quarter end over five years — so
that per-position contribution can be charted alongside the account-level series without the
client having to downsample. They add the same periodicity choice to their existing position
request and receive one observation per position per calendar period, aggregated by exactly the
same rules as the account endpoint.

**Why this priority**: Consistency between the two endpoints is what lets a client build a
combined account-and-position view at a single periodicity. It depends on the same aggregation
rules as User Story 1, so it follows it, but it is independently valuable and independently
testable.

**Independent Test**: Request the position time series for an account with at least two
positions and two years of ladder data, once with no periodicity and once with quarterly
periodicity. Verify each position appears exactly once per calendar quarter in which it has
data, and that each value matches the daily response for that position on the last business day
of that quarter within the resolved range.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Quarterly periodicity aggregates each position independently
  Given an account whose position ladder holds two positions with data continuously across 2025
  When I request the position time series for attribute "market_value" across 2025 with periodicity "quarter"
  Then the response contains 8 entries — one per position per calendar quarter
  And each entry's date is the first business day on or after the 1st of January, April, July or October
  And each entry's "market_value" equals that position's daily value on the last business day of that quarter

Scenario: A position with data in only part of the range appears only in the periods it covers
  Given an account whose position ladder holds a position with data only from 2025-04-01 to 2025-06-30
  When I request the position time series for that position for attribute "market_value" across 2025 with periodicity "quarter"
  Then the response contains exactly 1 entry for that position
  And that entry's date is the first business day on or after 2025-04-01

Scenario: Omitting periodicity preserves today's per-business-day position behaviour
  Given an account whose position ladder holds one position with data across January 2026
  When I request the position time series for attribute "market_value" across January 2026 with no periodicity parameter
  Then the response contains one entry per (business day, position) pair that has data
  And the response body is unchanged from the response produced before this feature existed, apart from the added periodicity field
```

---

### User Story 3 - Discoverable, Safely Rejected Periodicity Values (Priority: P3)

A developer integrating against either endpoint needs to know which periodicity values are
accepted and to be told clearly when they send something else, rather than silently receiving a
daily series they did not expect. Every response also states the periodicity that was actually
applied, so a client rendering a chart can label its axis without having to remember what it
asked for.

**Why this priority**: This hardens the contract and removes a class of silent
misinterpretation, but the feature is already useful without it. It is the smallest slice.

**Independent Test**: Send a request with an unsupported periodicity value and verify a
validation failure naming the supported set; send valid requests at each supported periodicity
and verify the applied periodicity is echoed in every response body.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: An unsupported periodicity value is rejected with a validation error
  Given an account with capital ingested across January 2026
  When I request the account time series for attribute "capital" with periodicity "fortnight"
  Then the request fails validation
  And the error message names the supported values: day, week, month, quarter, annual

Scenario: The applied periodicity is reported in the response
  Given an account with capital ingested across 2025
  When I request the account time series for attribute "capital" across 2025 with periodicity "month"
  Then the response reports its periodicity as "month"

Scenario: The default periodicity is reported when none was requested
  Given an account with capital ingested across 2025
  When I request the account time series for attribute "capital" across 2025 with no periodicity parameter
  Then the response reports its periodicity as "day"

Scenario: Explicitly requesting day periodicity behaves as the default
  Given an account with capital ingested across January 2026
  When I request the account time series for attribute "capital" across January 2026 with periodicity "day"
  Then the response is identical to the same request made with no periodicity parameter
```

---

### Edge Cases

- **Partial first period**: the resolved start date falls mid-period (e.g. a range starting
  2016-03-15 requested at annual periodicity). The period is still emitted, its date is the
  resolved start date rather than the calendar boundary that precedes the available data, and
  its value is the last observation on or before the end of that calendar period.
- **Partial last period**: the resolved end date falls mid-period (e.g. a range ending
  2026-09-22 requested at annual periodicity). The period is emitted with the last observation
  at or before the resolved end date — it is not dropped for being incomplete, and it is not
  extrapolated to the calendar period end.
- **Range shorter than one period**: a range of a few days requested at annual periodicity
  yields exactly one entry, dated at the resolved start, valued at the resolved end date's
  observation.
- **Calendar period containing no business day within the range**: the period is omitted
  entirely rather than emitted with null attribute values.
- **Position absent for part of the range**: a position with no data in a given calendar period
  produces no entry for that period; it is not carried forward across periods in which it does
  not appear.
- **Return-type attributes** (position return, weighted position return): the reported value is
  the last single-day return observed in the period, not a compounded period return. This is
  the stated last-observation rule applied uniformly, and is documented so consumers do not
  mistake it for a period return.
- **Date defaulting unchanged**: omitted start/end dates are resolved exactly as they are today,
  and periodicity is applied only after the range has been resolved — periodicity never changes
  which dates are in scope.
- **Existing validation unchanged**: invalid account names, missing or unsupported attributes,
  future end dates, inverted ranges and missing required sources fail exactly as they do now,
  regardless of the periodicity requested.
- **Unsupported periodicity plus another invalid input**: the request fails validation; the
  feature introduces no new ordering guarantee between simultaneous validation failures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both the account time series retrieval and the position time series retrieval MUST
  accept an optional periodicity input whose supported values are day, week, month, quarter and
  annual.
- **FR-002**: When periodicity is omitted, the system MUST behave exactly as it does today —
  one observation per business day — and MUST treat the effective periodicity as day.
- **FR-003**: When periodicity is explicitly day, the system MUST produce a response identical
  to the response produced when periodicity is omitted.
- **FR-004**: When periodicity is any value other than day, the system MUST divide the already
  resolved date range into consecutive, non-overlapping windows of that length and return at
  most one observation per window (per position, for the position endpoint).
- **FR-005**: Windows MUST be aligned to the real calendar rather than to the requested dates:
  week windows begin on Monday, month windows on the 1st of each calendar month, quarter
  windows on 1 January, 1 April, 1 July and 1 October, and annual windows on 1 January.
- **FR-006**: Each returned observation's reported date MUST be the start of its window, taken
  as the first business day on or after the window's calendar start date, except for the first
  window, whose reported date MUST be the resolved start date so that no reported date precedes
  the response's stated start of range.
- **FR-007**: Each attribute value on a returned observation MUST be that attribute's last
  observation within the window, bounded by the resolved date range — so the final window
  reports its value at the resolved end date, not at the window's calendar end.
- **FR-008**: All attributes on a single returned observation MUST be taken from the same source
  date, so that a period-level observation is internally consistent.
- **FR-009**: A window containing no observation within the resolved range MUST be omitted from
  the response rather than returned with absent or null attribute values.
- **FR-010**: Returned observations MUST be ordered by date ascending, matching the existing
  ordering guarantee of both endpoints.
- **FR-011**: Both responses MUST report the periodicity that was applied, including day when
  it was defaulted.
- **FR-012**: The periodicity field MUST be additive to the existing response bodies: every
  field present before this feature MUST remain present, with its existing name, meaning and
  value, so clients that ignore unknown fields are unaffected.
- **FR-013**: The stated start and end of the resolved range in each response MUST continue to
  report the resolved daily range, unchanged by the periodicity applied.
- **FR-014**: Both endpoints MUST reject an unsupported periodicity value with a validation
  failure that names the supported set, rather than silently applying a default.
- **FR-015**: Periodicity MUST be applied identically by both endpoints — same window
  alignment, same window-start dating, same last-observation rule, same omission of empty
  windows — with the position endpoint applying the rules independently per position.
- **FR-016**: Periodicity MUST NOT alter date defaulting, business-day adjustment, attribute
  support, forward-fill behaviour, or any existing validation rule or error response of either
  endpoint.
- **FR-017**: The supported periodicity values and their meaning MUST be discoverable from the
  endpoints' published interface description.

### Key Entities *(include if feature involves data)*

- **Periodicity**: The requested aggregation interval for a time series. One of a fixed, closed
  set of calendar intervals — day, week, month, quarter, annual — with day as the default when
  unspecified. Reported back on every response.
- **Period Window**: One calendar-aligned span within a resolved date range. Carries a reported
  date (its window start, clamped to the resolved range start for the first window) and the
  source date from which its attribute values were taken (the last observation in the window,
  bounded by the resolved range end). Zero or more windows exist per request; a window with no
  observation is not represented in the response.
- **Aggregated Observation**: One returned row for a window — dated at the window start and
  carrying each requested attribute's last in-window value. On the account endpoint, one per
  window; on the position endpoint, one per (window, position) pair that has data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consumer can retrieve a ten-year account history as annual, quarterly, monthly
  or weekly observations in a single request, with no client-side downsampling.
- **SC-002**: Requesting annual periodicity over a ten-full-calendar-year range returns exactly
  10 observations; monthly over the same range returns exactly 120.
- **SC-003**: For every supported periodicity, each returned value is verifiably identical to
  the value the same request returns at daily periodicity on that window's last in-range
  business day — confirmed across all attributes supported by both endpoints.
- **SC-004**: 100% of requests that omit the periodicity input return bodies identical to those
  returned before this feature, apart from the added periodicity field.
- **SC-005**: Every existing consumer of either endpoint continues to function without change,
  with no field removed, renamed or re-valued.
- **SC-006**: A ten-year request at annual, quarterly, monthly or weekly periodicity returns no
  slower than the equivalent daily request, and returns at most 1 observation per calendar
  period — reducing a ten-year daily series of roughly 2,600 observations to 10 (annual), 40
  (quarterly), 120 (monthly) or about 522 (weekly).
- **SC-007**: A developer sending an unsupported periodicity value learns the full set of
  supported values from the error response alone, without consulting documentation.

## Assumptions

- Periodicity is applied as a post-resolution aggregation step: the existing date defaulting,
  business-day adjustment and validation all run first and are untouched, and aggregation then
  operates on the resolved daily series.
- The effective periodicity is reported on every response — including day — rather than only
  when explicitly requested. An additive field is backward compatible for clients that ignore
  unknown fields, and always reporting it means a client never has to infer which rule was
  applied.
- Periodicity values are matched exactly as the lowercase tokens day, week, month, quarter and
  annual; any other value, including other casings and synonyms such as yearly, annually, daily
  or Q, is rejected. This mirrors the case-sensitive treatment of existing identifiers in these
  endpoints.
- Annual means the calendar year beginning 1 January — no fiscal or tax-year alignment is in
  scope.
- A week begins on Monday, consistent with the ISO calendar week used throughout the service's
  business-day handling.
- Quarters are calendar quarters beginning in January, April, July and October.
- Window start dates are reported as business days (the first business day on or after the
  calendar boundary), consistent with the existing endpoints' guarantee that every reported date
  is a business day.
- The first window's reported date is clamped to the resolved start date so that no entry date
  falls outside the response's stated range, which would otherwise break clients that plot
  entries within the stated range.
- The aggregation is a selection of existing daily values, not a recomputation: no new metric,
  averaging, summing or compounding is introduced by this feature.
- Both endpoints continue to serve the same attribute sets they support today; this feature adds
  no attributes and removes none.
- Requires the existing account time series and position time series retrieval capabilities,
  including their date resolution and forward-fill behaviour, to be in place and unchanged.
