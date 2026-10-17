# Feature Specification: Position Time Series API

**Feature Branch**: `005-position-timeseries-api`
**Created**: 2026-07-16
**Status**: Draft
**Input**: User description: "Create a position time series endpoint similar to /v1/accounts/{account_name}/timeseries, a grouping in the OpenAPI spec of 'Position Timeseries' and a proposed URL of /v1/accounts/{account_name}/position with a query-string array of 1+ position names. These names have text with symbols and spaces so must be adequately escaped. If no position names are specified then assume all positions in the given account are included. The first step is to validate that {account_name} is valid and matches an entry in /v1/accounts. The second step is to look up the distinct set of sub_account in that account through all history and to do an intersection of the possible values and requested inputs - if a requested position is not in the account it is silently ignored, not a cause for failure or error. There should be a helper method /v1/accounts/{account_name}/positions that takes no arguments beyond {account_name} and returns a list of all valid sub_accounts (aliased as a 'position') and their respective first/last position dates. Other arguments such as start/end dates should behave the same way as for the existing /v1/accounts/{account_name}/timeseries endpoint. The 'attribute' list is included but has a different list of valid entries - 'market_value', 'income', 'book_cost', 'pnl' are the same as for existing endpoint, 'capital' is no longer supported/valid here. In addition, 'close_price' and 'quantity' should be exposed. These map to the 'price' and 'quantity' columns in the account ladder.xlsx file. The response should be a suitable JSON payload for graphing - notably by the Dash app as a primary consumer; so consider options for a flat array of 'date', 'position' with a sub-array of attributes versus a true, nested by dimension structure where each date has an array of positions and each position has an array of attributes - whichever requires least work by a client Dash App to prepare for rendering in a line-chart"

## Clarifications

### Session 2026-07-16

- Q: A known account (present in `/v1/accounts`, e.g. via an ingested capital ledger) that has no ingested position ladder — what status code? → A: `422` — account name is valid, but the position ladder required source is missing, mirroring the account-timeseries endpoint's 404-vs-422 distinction (404 reserved for account names unknown to `/v1/accounts` entirely).
- Q: Should the endpoint cap the number of returned entries (positions × business days can be large, especially with no `position` filter)? → A: No cap — return however many entries the resolved positions/date-range produce, consistent with every other endpoint in this service having no pagination.
- Q: What concrete scale should the performance success criterion be pinned to? → A: A 5-year date range with 50 positions should return in under 10 seconds.
- Q: A position still actively held as of the ladder's last refresh (its rows reach the ladder's own `to_date`) — should its values be forward-filled up to the resolved end date, same as the account-level endpoint's staleness handling, while a genuinely divested position still stops permanently at its real last-active date? → A: Yes — forward-fill still-held positions. A position whose last recorded row lands exactly on the account's position-ladder `to_date` is treated as "still held, data just not yet refreshed" and is forward-filled to the resolved end date; a position whose rows stop earlier than the ladder's `to_date` is treated as genuinely divested and is never forward-filled past that point.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve a Per-Position Time Series for One or More Positions (Priority: P1)

An analyst calls the API with an account name and, optionally, one or more position names,
plus one or more attribute names (market_value, income, book_cost, pnl, close_price,
quantity), and receives back a single JSON time series covering every requested (or, if none
were named, every) position held in that account — one data point per position per business
day, ready to plot as one line per position per attribute without further reshaping.

**Why this priority**: This is the entire value of the feature — a single call that replaces
manually filtering the account-wide ladder file down to specific holdings to see how each one
performed over time.

**Independent Test**: For an account with an ingested position ladder covering several
positions, request `market_value` and `quantity` for two named positions over a known date
range. Verify the response contains one entry per business day per requested position that was
actually active in that range, each entry carrying both requested values, and that unrequested
positions are absent.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Retrieve a time series for two named positions and valid attributes
  Given account "test-portfolio" has an ingested position ladder containing positions
    "Apple Inc" and "Berkshire Hathaway Class B (BRK.B)"
  When a request is made for attributes "market_value" and "quantity", for positions
    "Apple Inc" and "Berkshire Hathaway Class B (BRK.B)", from 2024-01-02 to 2024-01-10
  Then the response status is 200
  And the response contains one entry per business day per position in that range
  And every entry contains a "market_value" value and a "quantity" value
  And the response body includes "_links.self", "_links.positions", "_links.attributes",
    and "_links.accounts" URLs

Scenario: No position names supplied defaults to every position in the account
  Given account "test-portfolio" has an ingested position ladder containing positions
    "Apple Inc", "Cash", and "Berkshire Hathaway Class B (BRK.B)"
  When a request is made for attribute "market_value" with no position names specified
  Then the response status is 200
  And entries are present for all three positions, including "Cash"

Scenario: An unrecognised position name is silently ignored, not rejected
  Given account "test-portfolio" has an ingested position ladder containing position
    "Apple Inc" but no position named "Nonexistent Corp"
  When a request is made for attribute "market_value" for positions "Apple Inc" and
    "Nonexistent Corp"
  Then the response status is 200
  And entries are present only for "Apple Inc"
  And no error is returned on account of "Nonexistent Corp"

Scenario: Position names containing spaces and symbols are correctly matched
  Given account "test-portfolio" has an ingested position ladder containing position
    "Berkshire Hathaway Class B (BRK.B)"
  When a request is made with that position name percent-encoded in the query string
  Then the response status is 200
  And entries are present for "Berkshire Hathaway Class B (BRK.B)"

Scenario: The "capital" attribute is no longer valid on this endpoint
  Given account "test-portfolio" has an ingested position ladder
  When a request is made for attribute "capital"
  Then the response status is 422
  And the response identifies "capital" as an unsupported attribute for this endpoint

Scenario: A known account with no ingested position ladder is rejected, but not as unknown
  Given account "capital-only-portfolio" has an ingested capital ledger but no position
    ladder
  When a request is made for attribute "market_value" for account "capital-only-portfolio"
  Then the response status is 422
  And the response identifies the position ladder as the missing required source

Scenario: Unknown account name is rejected
  Given no resource of any kind has been ingested for account "unknown-account"
  When a request is made for attribute "market_value" for account "unknown-account"
  Then the response status is 404

Scenario: Every requested position name fails to match returns zero entries, not an error
  Given account "test-portfolio" has an ingested position ladder containing position
    "Apple Inc" but no position named "Nonexistent Corp" or "Also Missing"
  When a request is made for attribute "market_value" for positions "Nonexistent Corp"
    and "Also Missing"
  Then the response status is 200
  And the response contains zero entries

Scenario: Missing mandatory attribute is rejected
  Given account "test-portfolio" has an ingested position ladder
  When a request is made with no attribute specified
  Then the response status is 422

Scenario: Start date after end date is rejected
  Given account "test-portfolio" has an ingested position ladder
  When a request is made for attribute "market_value" with start date 2024-02-01 and
    end date 2024-01-01
  Then the response status is 422

Scenario: End date in the future is rejected
  Given account "test-portfolio" has an ingested position ladder
  When a request is made for attribute "market_value" with an end date after today
  Then the response status is 422

Scenario: A position that was fully divested before the resolved end date has no
  entries after its last active date
  Given account "test-portfolio" has an ingested position ladder whose own to_date is
    its ingestion-time value (today minus two business days), and in which position
    "Sold Corp" was fully divested several business days before that to_date
  When a request is made for attribute "market_value" for position "Sold Corp" ending
    on the most recent business day
  Then the response status is 200
  And "Sold Corp" has no entries after its own last recorded (divestment) date

Scenario: A still-held position is forward-filled to the resolved end date when the
  ladder itself is stale
  Given account "test-portfolio" has an ingested position ladder whose own to_date is
    its ingestion-time value (today minus two business days), and in which position
    "Apple Inc" has a recorded row on that to_date (its last ingested date) with a
    known market_value
  When a request is made for attribute "market_value" for position "Apple Inc" ending
    on the most recent business day
  Then the response status is 200
  And "Apple Inc" has entries through the resolved end date, with every entry after
    its last ingested date carrying the same forward-filled market_value
```

---

### User Story 2 - Discover Valid Positions and Their Active Date Ranges (Priority: P2)

An analyst (or a client application, such as a position picker in the Dash app) calls a
helper endpoint with just the account name and receives back every position ever recorded in
that account's history, aliased consistently with the main endpoint's terminology, along with
each position's first and last recorded date — so valid position names and sensible default
date ranges can be discovered without first calling the main endpoint.

**Why this priority**: Removes guesswork around valid position names (which may contain
spaces and symbols) and lets a client pre-populate a position selector before a user makes
their first time-series request.

**Independent Test**: With an account holding three positions, two still active and one fully
divested, call the helper endpoint and verify all three are listed with their own accurate
first/last recorded dates, distinguishable from one another.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Enumerate all positions held in an account
  Given account "test-portfolio" has an ingested position ladder containing positions
    "Apple Inc", "Cash", and "Sold Corp"
  When a request is made to the positions endpoint for account "test-portfolio"
  Then the response status is 200
  And all three positions appear, each with its own first and last recorded date
  And the response body includes a "_links.self" URL

Scenario: Unknown account name is rejected
  Given no resource of any kind has been ingested for account "unknown-account"
  When a request is made to the positions endpoint for account "unknown-account"
  Then the response status is 404

Scenario: A known account with no ingested position ladder is rejected, but not as unknown
  Given account "capital-only-portfolio" has an ingested capital ledger but no position
    ladder
  When a request is made to the positions endpoint for account "capital-only-portfolio"
  Then the response status is 422
```

---

### User Story 3 - Discover Which Attributes the Position Endpoint Accepts (Priority: P3)

An analyst or client application calls a metadata endpoint to discover which attribute names
are valid specifically for the position time series endpoint — a different set than the
account-level time series endpoint, since `capital` is excluded and `close_price`/`quantity`
are added — without hard-coding or guessing the list.

**Why this priority**: Supports the same self-describing API discovery already established
for the account-level endpoint; lower priority than User Stories 1–2 because a client can
still function using a hard-coded list, just less robustly to future changes.

**Independent Test**: Call the position-attribute metadata endpoint with no other setup
required. Verify it returns exactly the six supported attributes with a description each, and
that this list matches exactly what User Story 1 accepts (and excludes `capital`).

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Retrieve the list of supported position-attribute names
  When a request is made to the position-attribute metadata endpoint
  Then the response status is 200
  And the response lists all six supported attributes: market_value, income, book_cost,
    pnl, close_price, and quantity
  And "capital" does not appear in the list
  And each listed attribute includes a human-readable description
  And the response body includes a "_links.self" URL
```

---

### Edge Cases

- What happens when every requested position name fails to match the account's recorded
  sub_accounts? → Accepted; the response is 200 with an empty set of entries, consistent
  with individual mismatches being silently ignored rather than treated as an error.
- What happens when a position is requested that is valid for the account but has no
  recorded activity anywhere in the resolved date range (e.g., bought after the range ends,
  or sold before it starts)? → Accepted; that position simply contributes zero entries, it
  is not an error.
- What happens when a still-held position's last recorded row is older than the resolved
  end date because the account's position ladder itself has not been refreshed since then?
  → Its last recorded values are forward-filled through the resolved end date, since its
  last row lands exactly on the ladder's own to_date (the signal that it is still held, not
  divested) — mirroring the account-level endpoint's staleness handling.
- What happens when a position was genuinely divested (its rows stop before the ladder's
  own to_date)? → It is never forward-filled past its actual last recorded date, even if
  other still-held positions in the same response are forward-filled further.
- What happens when the synthetic "Cash" sub-account is requested by name, or included via
  the "no positions specified" default? → Treated like any other position; it is a real
  sub_account in the ladder and is included.
- What happens when the resolved start date falls before the account's own earliest
  recorded position-ladder date? → Rejected with a 422 error, since the position ladder is
  the sole required source for this endpoint and no data exists before that point for any
  position.
- What happens when the same position name is supplied more than once in the query string?
  → Treated as a single request for that position; duplicates do not produce duplicate
  entries.
- What happens when a position name's matching is case-sensitive vs. case-insensitive? →
  Matching is exact and case-sensitive, consistent with how sub_account names are matched
  elsewhere in this service.
- What happens when a non-business-day start/end date is supplied? → Silently adjusted to
  the next business day (or backward if that would land after today), exactly as the
  account-level time series endpoint behaves.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a GET endpoint that returns a time series scoped to one
  or more named positions within a named account: one entry per business day per position
  actually active on that day, each entry carrying the requested attribute values.
- **FR-002**: The account name MUST be a mandatory path parameter. An account name matching
  no ingested resource of any kind (absent from `/v1/accounts` entirely) MUST be rejected
  with a 404 response. An account name that is known (present in `/v1/accounts`, e.g. via an
  ingested capital ledger) but has no ingested position ladder MUST be rejected with a 422
  error identifying the missing position ladder — this endpoint's entire domain is sourced
  from the position ladder, so a capital-ledger-only account cannot be served, but it is not
  treated as an unknown account.
- **FR-003**: The endpoint MUST accept zero or more repeated `position` query parameters.
  Position values MUST be accepted through standard URL percent-encoding so that names
  containing spaces and symbols (e.g. parentheses, ampersands, periods) are correctly
  received and decoded.
- **FR-004**: If zero `position` values are supplied, the effective position set MUST default
  to every distinct sub_account recorded in the account's position ladder across its full
  history, including the synthetic "Cash" sub-account.
- **FR-005**: If one or more `position` values are supplied, each MUST be compared, exactly
  and case-sensitively, against the distinct set of sub_account names recorded in the
  account's position ladder across its full history. A supplied value with no match MUST be
  silently dropped — it MUST NOT cause the request to fail or be flagged as an error. The
  effective position set is the intersection of supplied values and recorded sub_accounts.
  Duplicate supplied values MUST be treated as a single position.
- **FR-006**: If the effective position set (after FR-004/FR-005) is empty — either because
  every supplied name failed to match, or because the account's ladder itself has no
  sub_accounts — the request MUST still succeed (200) and return a response with zero
  entries, not an error.
- **FR-007**: At least one attribute MUST be specified, passed as one or more repeated
  `attribute` query parameters. Requests with zero attributes MUST be rejected with a 422
  error.
- **FR-008**: Each requested attribute MUST be one of the supported set for this endpoint:
  `market_value`, `income`, `book_cost`, `pnl`, `close_price`, `quantity` (all lowercase).
  `capital` — valid on the account-level time series endpoint — MUST NOT be accepted here.
  Any other unsupported attribute name MUST be rejected with a 422 error listing the
  supported attribute names for this endpoint.
- **FR-009**: The system MUST accept optional `start` and `end` date parameters (calendar
  dates, no time component), resolved using the same defaulting, business-day-adjustment,
  and validation rules as the existing account-level time series endpoint: `start` defaults
  to the account's own earliest recorded position-ladder date; `end` defaults to the most
  recent business day before today; a non-business-day date is silently adjusted forward to
  the next business day (or backward if that would place it after today); a resolved start
  after the resolved end, or a supplied end later than today, MUST be rejected with a 422
  error.
- **FR-010**: If the resolved start date falls before the account's own earliest recorded
  position-ladder date, the request MUST be rejected with a 422 error identifying that no
  data exists before that date, mirroring the missing-source validation on the account-level
  endpoint (here there is only one possible required source: the position ladder).
- **FR-011**: For each position in the effective set and each requested attribute, values
  MUST be sourced directly from that position's own recorded position-ladder rows for each
  date: `market_value` from the ladder's market value field, `book_cost` from the ladder's
  book cost field, `income` from the ladder's cumulative income field, `close_price` from
  the ladder's price field, `quantity` from the ladder's quantity field.
- **FR-012**: The `pnl` attribute MUST be computed per position, per date, as
  `income + market_value - book_cost`, using that position's own recorded values for all
  three terms — no dependency on the capital ledger, unlike the account-level `pnl`.
- **FR-013**: A given position's entries MUST be limited to the dates on which that position
  is considered active. A position whose last recorded position-ladder row lands exactly on
  the account's position-ladder `to_date` (i.e. still held as of the last ingestion, not yet
  divested) MUST have its last recorded attribute values forward-filled through the resolved
  end date, exactly mirroring the account-level endpoint's handling of a ladder that is not
  as current as today. A position whose recorded rows stop earlier than the account's
  position-ladder `to_date` MUST be treated as genuinely divested at that date and MUST NOT
  be forward-filled past it. The system MUST NOT fabricate or zero-fill entries before a
  position's own first recorded date or after a genuinely divested position's last recorded
  date, even when other positions in the same response have entries on those dates.
- **FR-014**: The response MUST be structured as a flat, non-nested list of entries, each
  identifying its date, its position name, and the values of only the requested attributes
  for that (date, position) pair — one entry per (date, position) combination that has data —
  so that a charting client can plot one line per position (or per position/attribute pair)
  directly from the entry list without first regrouping or unnesting the response by
  dimension.
- **FR-015**: The response MUST include HATEOAS `_links`, at minimum a `self` link, plus
  links to the position-attribute metadata endpoint, the positions-enumeration endpoint
  (FR-016), and the accounts-enumeration endpoint.
- **FR-016**: The system MUST expose a helper GET endpoint, scoped to an account name and no
  other parameters, that returns every distinct sub_account recorded in that account's
  position ladder across its full history — aliased as "position" in the response — each with
  its own first and last recorded date, plus HATEOAS `_links`. This endpoint MUST use the
  same account-validation rule as FR-002 (404 if the account name is unknown to `/v1/accounts`
  entirely; 422 if the account is known but has no ingested position ladder).
- **FR-017**: The system MUST expose a metadata endpoint that returns every attribute name
  supported by this endpoint (FR-008's set) together with a human-readable description, plus
  HATEOAS `_links`. This list MUST stay in sync with the attribute set enforced by FR-008 and
  MUST NOT include `capital`.
- **FR-018**: All error responses MUST use RFC 7807 Problem Details format, consistent with
  the existing ladder, capital ledger, and account-level time series endpoints.
- **FR-019**: "Business day" MUST mean Monday through Friday, with no public holiday
  calendar applied, consistent with the existing account-level time series endpoint.
- **FR-020**: The endpoint MUST NOT impose an artificial cap on the number of returned
  entries or require pagination; response size scales naturally with the number of positions
  in the effective set multiplied by the number of business days in the resolved range,
  consistent with no other endpoint in this service imposing pagination.

### Key Entities

- **Position Time Series**: The response to the main GET endpoint — the requested account
  name, the resolved date range, the effective position set, the list of requested
  attributes, a flat list of per-(date, position) entries, and HATEOAS `_links`.
- **Position Time Series Entry**: One row of the time series — a business-day date, a
  position name, and a value for each requested attribute that position has recorded for
  that date.
- **Position Summary**: One entry in the positions-enumeration endpoint's response — a
  position name (aliased from sub_account) and its earliest and latest recorded date.
- **Position Attribute Definition**: One entry in this endpoint's metadata response — an
  attribute name and a human-readable description.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A correctly formed request for a known account, valid attributes, and a 5-year
  date range (~1,300 business days) across all 50 positions in a typical large account
  returns a complete time series within 10 seconds.
- **SC-002**: 100% of (business day, active position) combinations within the resolved date
  range appear in the response, with no gaps — accounting for genuinely divested positions
  stopping at their real last active date, and still-held positions being forward-filled
  through the resolved end date when the ladder itself is stale — and no entries fabricated
  before a position's own first recorded date.
- **SC-003**: 100% of requests naming one or more unrecognised position values alongside at
  least one recognised value (or an empty effective set) still return a 200 response
  containing data for every recognised value — never a 4xx error caused solely by an
  unrecognised position name.
- **SC-004**: Requests naming an unsupported attribute (including `capital`), an unknown
  account, or an invalid date range are rejected with a descriptive error in under 1 second,
  and never return a partial or silently-incomplete time series.
- **SC-005**: The position-attribute metadata endpoint's list of attribute names is always
  identical to the set of attribute names the main endpoint accepts, and never includes
  `capital` (100% match, verified by test).
- **SC-006**: The positions-enumeration endpoint's reported first/last dates match the
  underlying position ladder's actual first and last recorded dates, per position, for 100%
  of ingested accounts.
- **SC-007**: A client building a per-position line chart (e.g. the Dash app) can do so
  directly from the response's entry list — grouping by position name and plotting each
  requested attribute — without needing to first restructure the response into a different
  shape.

## Assumptions

- The proposed URL forms are used verbatim as given: the main endpoint is singular
  (`/v1/accounts/{account_name}/position`) and the helper enumeration endpoint is plural
  (`/v1/accounts/{account_name}/positions`). This asymmetry is intentional, matching the
  user's description, and is not treated as an inconsistency to reconcile.
- Because every attribute on this endpoint (including `pnl`) is derivable from the position
  ladder alone, this endpoint has exactly one required source. There is no equivalent here to
  the account-level endpoint's per-attribute "missing required source" distinction between
  attributes needing one ledger versus another — the only source-availability check is
  whether the account has an ingested position ladder at all (FR-002).
- A position's entries are limited to its own active lifecycle: never before its first
  recorded row, and never after its last recorded row *unless* that last row lands exactly
  on the account's position-ladder `to_date` — the signal that the position is still held
  and the ladder simply has not been refreshed past that point yet, in which case its last
  known values are forward-filled through the resolved end date (mirroring the account-level
  endpoint's own staleness handling). A position whose rows stop earlier than the ladder's
  `to_date` is genuinely divested and is never forward-filled. Silently omitting
  out-of-lifecycle dates (rather than fabricating zero-value or null entries) was chosen
  since a position that has not yet been bought, or has been genuinely divested, has no
  meaningful market_value/quantity/etc. to report, and a client plotting a line chart
  naturally wants the line to simply not exist over that range, not dip to zero.
- The synthetic "Cash" sub-account is treated as an ordinary position: it is included in the
  "no positions specified" default and can be explicitly requested/matched by name, since it
  is a normal row in the position ladder with no exception carved out by the user's
  description.
- An empty effective position set (FR-006) — whether from all-mismatched inputs or an account
  ladder with no recorded sub_accounts — returns a 200 response with zero entries rather than
  an error, consistent with the "silently ignored, not a cause for failure" instruction
  extended to its logical extreme.
- Position name matching is exact and case-sensitive, consistent with how sub_account/ticker
  identifier matching already behaves elsewhere in this service (position ladder enrichment).
- A dedicated position-attribute metadata endpoint (User Story 3) is added even though not
  explicitly requested, mirroring the existing account-level time series endpoint's
  established HATEOAS/self-describing-API convention (its own metadata endpoint), so a client
  is never left guessing which attribute set applies to which endpoint.
- The response's flat, one-entry-per-(date, position) shape (FR-014) was chosen over a
  dimension-nested structure (e.g. dates containing arrays of positions containing arrays of
  attributes) because it requires no client-side unnesting before use in typical charting
  workflows (such as a Dash/Plotly line chart grouped by position) — the entry list can be
  used directly as tabular/"long format" data.
- These endpoints require no authentication, consistent with the existing ladder, capital
  ledger, and account-level time series endpoints in this locally hosted service.
- Both new endpoints (and the helper enumeration endpoint) are read-only and perform no
  writes to the underlying stored position ladder.
