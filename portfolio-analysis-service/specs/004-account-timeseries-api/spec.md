# Feature Specification: Account Time Series API

**Feature Branch**: `004-account-timeseries-api`
**Created**: 2026-07-11
**Status**: Draft
**Input**: User description: "Create a 'GET' endpoint on the portfolio-analysis-service that takes a variety of arguments and returns a JSON payload with a time-series and the requested attributes per-date. It should derive this data from ingested capital and sub-account ledgers, joining as appropriate. If data is missing from a required source then the endpoint returns an error. If the underlying data is not as recent as today then the latest records can be forward-filled until today without being considered an error. There should be a metadata query alongside the GET (compliant with RESTful, HATEOS best practices) to describe te attributes that can be requested. Another similar endpoint should enumerate the available accounts and their earliest/latest dates. For the main 'GET' the mandatory arguments are the 'account name' (which must validate against one that has been ingested) and at least one 'attribute' (many can be requested). Optionally a start/end date (no time element) can be provided; this has validation that the start must be before the end and the end must not be in the future; if either is not provided it assumes the earliest date in the account (for start) or the previous business day if no end date specified. If inputs are not working days then it is adjusted to the next working day without being an error. The supported attributes are as follows: "capital" (the capital value on that date), "income" (the total income received up until that date), "book_cost" (from the capital ladder's "book_value" field), "market_value" (the sum of the 'market_value' from the sub-account ledger for that date), "PnL" ("Income"+"Market_Value"-"Book_cost" for that date). This endpoint is an aggregation over sub-accounts so should have a single entry per business date between the start/end dates."

## Clarifications

### Session 2026-07-11

- Q: How should multiple `attribute` values be passed in the query string? → A: Repeated parameter: `?attribute=capital&attribute=income` (matches idiomatic REST/OpenAPI array-query-param convention and FastAPI's native list-query-param support).
- Q: Should the `PnL` attribute's wire-format name match the user's literal casing, or be normalized to lowercase snake_case like the other four attributes? → A: Normalize to `pnl` (lowercase), consistent with every other field name in this service (`row_count`, `book_cost`, `market_value`, etc. are all lowercase snake_case with no exceptions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve a Multi-Attribute Time Series for an Account (Priority: P1)

An analyst calls the API with an account name and one or more attribute names (capital,
income, book_cost, market_value, pnl) and receives back a single JSON time series: one entry
per business day, each carrying the requested attribute values. Values are derived by joining
the account's ingested capital ledger and position ladder, and the series is forward-filled up
to today if the underlying records don't yet cover the most recent days.

**Why this priority**: This is the entire value of the feature — a single call that replaces
manually opening and cross-referencing two separate stored ledgers to answer "what was this
account worth, and how did it get there, over time."

**Independent Test**: For an account with both a capital ledger and a position ladder ingested,
request `capital`, `market_value`, and `pnl` over a known date range. Verify the response has
exactly one entry per business day in that range, every entry carries all three requested
values, and `pnl` is arithmetically consistent with the other two.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Retrieve a time series for a known account and valid attributes
  Given account "test-portfolio" has an ingested capital ledger and position ladder
  When a request is made for attributes "capital" and "market_value" from 2024-01-02 to 2024-01-10
  Then the response status is 200
  And the response contains one entry per business day from 2024-01-02 to 2024-01-10
  And every entry contains a "capital" value and a "market_value" value
  And the response body includes "_links.self", "_links.attributes", and "_links.accounts" URLs

Scenario: Underlying data older than today is forward-filled, not treated as an error
  Given account "test-portfolio" has a capital ledger whose latest recorded date is before today
  When a request is made for attribute "capital" ending on the most recent business day
  Then the response status is 200
  And entries after the capital ledger's latest recorded date carry the last recorded value

Scenario: Requesting an attribute whose required source was never ingested is rejected
  Given account "ladder-only-portfolio" has an ingested position ladder but no capital ledger
  When a request is made for attribute "capital"
  Then the response status is 422
  And the response identifies that the capital ledger source is missing for this account

Scenario: Missing mandatory attribute is rejected
  Given account "test-portfolio" has an ingested capital ledger and position ladder
  When a request is made with no attribute specified
  Then the response status is 422

Scenario: Unknown account name is rejected
  Given no ledger of any kind has been ingested for account "unknown-account"
  When a request is made for attribute "capital" for account "unknown-account"
  Then the response status is 404

Scenario: Start date after end date is rejected
  Given account "test-portfolio" has an ingested capital ledger and position ladder
  When a request is made with start date 2024-02-01 and end date 2024-01-01
  Then the response status is 422

Scenario: End date in the future is rejected
  Given account "test-portfolio" has an ingested capital ledger and position ladder
  When a request is made with an end date after today
  Then the response status is 422

Scenario: Non-business-day start and end dates are silently adjusted
  Given account "test-portfolio" has an ingested capital ledger and position ladder
  When a request is made with a start date that falls on a Saturday
  Then the response status is 200
  And the first entry in the response is dated on or after the following Monday
```

---

### User Story 2 - Discover Available Attributes via Metadata (Priority: P2)

An analyst (or a client application) calls a metadata endpoint to discover which attribute
names are valid for the time series endpoint, what each one means, and which underlying
source it comes from, without needing to consult external documentation.

**Why this priority**: Supports self-describing API discovery (RESTful/HATEOAS expectation)
and lets client applications validate attribute names before calling User Story 1, rather than
hard-coding the attribute list.

**Independent Test**: Call the metadata endpoint with no other setup required. Verify it
returns all five supported attributes with a name and description each, and that this list
matches exactly the set of attribute names User Story 1 accepts.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Retrieve the list of supported time series attributes
  When a request is made to the attribute metadata endpoint
  Then the response status is 200
  And the response lists all five supported attributes: capital, income, book_cost, market_value, and pnl
  And each listed attribute includes a human-readable description
  And the response body includes a "_links.self" URL
```

---

### User Story 3 - Enumerate Ingested Accounts and Their Date Ranges (Priority: P2)

An analyst calls an endpoint to list every account that has at least one ingested resource
(capital ledger and/or position ladder), along with the earliest and latest available date for
each ingested resource, so they know which account names and date ranges are valid before
calling User Story 1.

**Why this priority**: Removes guesswork around valid account names and date ranges, and
surfaces accounts that only have one of the two resources ingested (relevant to which
attributes will be available for that account).

**Independent Test**: With two accounts ingested (one with both resources, one with only a
capital ledger), call the accounts endpoint and verify both are listed with accurate
per-resource date ranges, and that the capital-only account shows no position-ladder range.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Enumerate accounts with both resources ingested
  Given account "test-portfolio" has an ingested capital ledger and position ladder
  When a request is made to the accounts endpoint
  Then the response status is 200
  And "test-portfolio" appears with its capital ledger date range and position ladder date range
  And the response body includes a "_links.self" URL

Scenario: Enumerate an account with only one resource ingested
  Given account "capital-only-portfolio" has an ingested capital ledger but no position ladder
  When a request is made to the accounts endpoint
  Then the response status is 200
  And "capital-only-portfolio" appears with a capital ledger date range and no position ladder range
```

---

### Edge Cases

- What happens when an account has a position ladder but no capital ledger, and `market_value`
  (not requiring the capital ledger) is requested? → Accepted; only sources required by the
  requested attributes are checked.
- What happens when the requested start date is earlier than a required source's earliest
  recorded date? → Rejected with a 422 error naming the source and the earliest date it
  actually supports (no backward-fill).
- What happens when adjusting a non-business-day date forward would push it beyond today
  (only possible when today itself falls on a weekend)? → The date is instead adjusted
  backward to the most recent business day on or before today, preserving the "no future
  dates" guarantee.
- What happens when forward/backward business-day adjustment causes the resolved start date
  to fall after the resolved end date? → Rejected with a 422 error, same as an explicit
  start-after-end request.
- What happens when `pnl` is requested but only one of the two underlying sources exists for
  the account? → Rejected with a 422 error naming the missing source, since `pnl` depends on
  data from both.
- What happens when an unsupported attribute name is requested? → Rejected with a 422 error
  listing the supported attribute names.
- What happens when a single business day is requested (start equals end)? → Accepted; the
  response contains exactly one entry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a GET endpoint that returns a time series for a named
  account: one entry per business day in a resolved date range, each entry carrying the
  requested attribute values for that date.
- **FR-002**: The account name MUST be a mandatory parameter and MUST be validated against
  accounts that have at least one ingested resource (capital ledger and/or position ladder);
  an account name matching no ingested resource of any kind MUST be rejected with a 404
  response.
- **FR-003**: At least one attribute MUST be specified, passed as a repeated `attribute` query
  parameter (e.g. `?attribute=capital&attribute=income`) so multiple attributes can be
  requested in a single call. Requests with zero attributes MUST be rejected with a 422 error.
- **FR-004**: Each requested attribute MUST be one of the supported set: `capital`, `income`,
  `book_cost`, `market_value`, `pnl` (all lowercase, matching the existing snake_case naming
  convention used throughout this service's other field names). Any other attribute name MUST
  be rejected with a 422 error listing the supported attribute names.
- **FR-005**: The system MUST accept optional `start` and `end` date parameters (calendar
  dates, no time component).
- **FR-006**: If `start` is omitted, it MUST default to the earliest date on which all sources
  required by the requested attributes have recorded data (i.e., the later of each required
  source's own earliest recorded date), ensuring the default range does not itself trigger a
  missing-data error.
- **FR-007**: If `end` is omitted, it MUST default to the most recent business day before
  today.
- **FR-008**: A resolved or supplied `start`/`end` date that falls on a non-business day MUST
  be silently adjusted forward to the next business day; if that adjustment would place the
  date after today, it MUST instead be adjusted backward to the most recent business day on or
  before today. This adjustment MUST NOT be treated as an error.
- **FR-009**: After defaulting and business-day adjustment, if the resolved start date is after
  the resolved end date, the request MUST be rejected with a 422 error.
- **FR-010**: A supplied `end` date that is later than today (before any adjustment) MUST be
  rejected with a 422 error.
- **FR-011**: For each requested attribute and each date in the resolved range, the value MUST
  be derived by forward-filling the most recent recorded observation in the attribute's
  required source(s) on or before that date — including forward-filling past the source's own
  latest recorded date, up to the resolved end date, when that source is not as current as
  today.
- **FR-012**: The `book_cost` attribute MUST be sourced from the capital ledger's `book_value`
  field. The `capital` attribute MUST be sourced from the capital ledger's `capital` field.
  The `income` attribute MUST be sourced from the capital ledger's `income` field (already a
  running total as of each recorded date).
- **FR-013**: The `market_value` attribute MUST be the sum of the position ladder's
  `market_value` field across all sub-accounts present in the ladder for the account on that
  date (including the synthetic Cash sub-account).
- **FR-014**: The `pnl` attribute MUST be computed as `income + market_value - book_cost` for
  each date, and requires both the capital ledger (for `income` and `book_cost`) and the
  position ladder (for `market_value`) to be available for the account, regardless of whether
  `income`, `book_cost`, or `market_value` were separately requested.
- **FR-015**: If a requested attribute's required source does not exist for the account, or
  does not have any recorded observation on or before the resolved start date, the entire
  request MUST be rejected with a 422 error identifying the missing source and the affected
  attribute(s). The endpoint MUST NOT return a partial time series with missing or null values
  for the affected attribute.
- **FR-016**: The response MUST include HATEOAS `_links`, at minimum a `self` link, plus links
  to the attribute-metadata endpoint and the accounts-enumeration endpoint.
- **FR-017**: The system MUST expose a metadata endpoint that returns every supported
  attribute name together with a human-readable description and its source ledger(s), plus
  HATEOAS `_links`. This list MUST stay in sync with the attribute set enforced by FR-004.
- **FR-018**: The system MUST expose an accounts-enumeration endpoint that returns every
  account with at least one ingested resource, together with the earliest and latest
  available date for each ingested resource (capital ledger and/or position ladder)
  separately, plus HATEOAS `_links`. An account with only one resource ingested MUST show a
  date range for that resource only.
- **FR-019**: All error responses MUST use RFC 7807 Problem Details format, consistent with
  the existing ladder and capital ledger endpoints.
- **FR-020**: "Business day" MUST mean Monday through Friday, with no public holiday
  calendar applied, consistent with the existing ladder and capital ledger expansion logic.

### Key Entities

- **Account Time Series**: The response to the main GET endpoint — the requested account name,
  the resolved date range, the list of requested attributes, one entry per business day, and
  HATEOAS `_links`.
- **Time Series Entry**: One row of the time series — a business-day date plus a value for
  each requested attribute.
- **Attribute Definition**: One entry in the metadata endpoint's response — an attribute name,
  a human-readable description, and the source ledger(s) it is derived from.
- **Account Summary**: One entry in the accounts-enumeration endpoint's response — an account
  name and, for each ingested resource (capital ledger, position ladder), its earliest and
  latest available date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A correctly formed request for a known account, valid attributes, and a
  multi-year date range (up to 10 years / ~2,600 business days) returns a complete time series
  within 5 seconds.
- **SC-002**: 100% of business days in the resolved date range appear in the response, each
  with a value for every requested attribute — no gaps, regardless of whether the value was
  directly recorded or forward-filled.
- **SC-003**: Requests naming an unsupported attribute, an unknown account, an invalid date
  range, or a range with a missing required source are rejected with a descriptive error in
  under 1 second, and never return a partial or silently-incomplete time series.
- **SC-004**: The attribute-metadata endpoint's list of attribute names is always identical to
  the set of attribute names the main endpoint accepts (100% match, verified by test).
- **SC-005**: The accounts-enumeration endpoint's reported date ranges match the underlying
  stored resources' actual first and last recorded dates for 100% of ingested accounts.

## Assumptions

- Account name validity (FR-002) is a coarser check than per-attribute source availability
  (FR-015): a name is "known" if either resource has been ingested for it, but a specific
  attribute request can still fail if its required source is absent. This distinction is
  implied by the user's description treating "unknown account" and "missing required source"
  as two separate rules.
- The default `start` date (FR-006) is deliberately the *later* of the required sources'
  earliest dates, not the earliest across all sources — a range that begins before a required
  source's data exists would immediately violate the "missing data is an error" rule, so this
  is the only self-consistent default.
- No backward-fill is performed before a source's earliest recorded date; only forward-fill
  (extending the latest known value) is used to cover gaps up to today. This mirrors the
  existing capital ledger and position ladder expansion logic, which is also forward-fill-only.
- Missing-data handling is fail-fast for the whole request (FR-015), not per-entry/per-attribute
  partial results with nulls. This mirrors the existing ingestion endpoints' "all-or-nothing"
  validation pattern (e.g., price-coverage and identifier-mapping failures on the ladder
  endpoint) rather than introducing a new partial-success shape.
- The accounts-enumeration endpoint reports the two resources' date ranges separately rather
  than merging them into one combined range, consistent with capital ledgers and position
  ladders being independently stored and versioned resources per account (established by the
  existing capital ledger ingestion feature).
- `market_value` aggregation includes the synthetic Cash sub-account row (priced at 1.0 GBP by
  the existing enrichment logic), since Cash is a normal row in the position ladder and the
  user's description does not carve out an exception for it.
- These endpoints require no authentication, consistent with the existing ladder and capital
  ledger endpoints in this locally hosted service.
- Both new enumeration/metadata endpoints and the main time series endpoint are read-only and
  perform no writes to the underlying stored ledgers.
