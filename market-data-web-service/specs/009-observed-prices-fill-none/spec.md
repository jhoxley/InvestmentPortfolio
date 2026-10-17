# Feature Specification: Observed-Only Price History (`fill=none`)

**Feature Branch**: `026-mds-observed-prices-fill-none`
**Spec Directory**: `specs/009-observed-prices-fill-none`
**Created**: 2026-10-03
**Status**: Draft
**Input**: User description: "Add an option to the security price history endpoint (GET /securities/{identifier}/history) to return only observed market prices, without the forward-fill/back-fill gap filling introduced in 006-price-series-fill. Add a query parameter fill with values \"all\" (the default, keeping today's gap-filled behaviour and price list exactly as now) and \"none\" (only dates that have a real observation from the primary source, cache or local fallback file). When currency conversion is requested with fill=none, each observed price is converted using the gap-filled FX rate for that date, as today. In both modes the response gains two additive fields: first_observed_date and last_observed_date for the instrument, as far as the service knows. Separately, when a request asks for history before the earliest cached date and the data source has no data for that earlier segment, the cache must remember that no data exists before the earliest observation, so later requests don't call the data source again for the same empty segment; this memory must be invalidated if a later fetch does find earlier data, and must be visible in logs. Local-only fallback files behave the same way (fill=none returns the file's raw rows within the range). This is needed so a Value-at-Risk calculation in portfolio-analysis-service can tell real returns from filled flat prices; filled prices must never be presented as observations when fill=none."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Observed-Only Price History for Risk Calculations (Priority: P1)

A risk analyst (via the portfolio analysis service) needs the genuine day-to-day price moves of a security to compute Value-at-Risk from a distribution of historical returns. Today the history endpoint always returns a complete Mon–Fri series where non-trading days carry a repeated price, which injects artificial zero-return days into the distribution and understates risk. The consumer asks for the same history with observed prices only, and receives entries exclusively for dates where a real market observation exists — no carried-forward or carried-back values.

**Why this priority**: This is the entire reason for the feature. Without it, no downstream return distribution can distinguish a true flat day from a filled non-trading day, and the VaR result is systematically wrong.

**Independent Test**: Request history for a range containing a known mid-week market holiday with observed-only mode selected, and assert the holiday date is absent from the response while every trading date is present with its own distinct observed price. Delivers value on its own, with no other story implemented.

**Acceptance Scenarios** *(MANDATORY — Gherkin format; these become `.feature` file scenarios)*:

```gherkin
Scenario: Observed-only mode omits non-trading days
  Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
  And 2025-01-03 is a market holiday with no observation
  When a consumer requests price history from 2025-01-02 to 2025-01-06 with fill "none"
  Then the response status is 200
  And the response contains exactly 2 price entries
  And the entries are for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
  And no entry exists for 2025-01-03

Scenario: Observed-only mode does not back-fill before the first observation
  Given the data source has no observation before 2025-01-06
  And the first available price is 2025-01-06 at 100.00
  When a consumer requests price history from 2025-01-02 to 2025-01-07 with fill "none"
  Then the response contains no entry for 2025-01-02 or 2025-01-03
  And the earliest entry in the response is 2025-01-06

Scenario: Observed-only mode does not forward-fill a stale end of range
  Given today is a business day
  And the data source has a price for T-2 at 100.00 but no observation for T-1 or today
  When a consumer requests price history ending today with fill "none"
  Then the response contains no entry for T-1 or today
  And the latest entry in the response is for T-2

Scenario: Default behaviour is unchanged when fill is not supplied
  Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
  And 2025-01-03 is a market holiday with no observation
  When a consumer requests price history from 2025-01-02 to 2025-01-06 with no fill parameter
  Then the response contains 3 price entries
  And the entry for 2025-01-03 carries the forward-filled price 100.00

Scenario: Explicit fill "all" matches the default behaviour exactly
  Given a request for price history over a range containing non-trading days
  When the consumer requests it once with fill "all" and once with no fill parameter
  Then both responses contain an identical list of price entries

Scenario: Unrecognised fill value is rejected
  Given a consumer requests price history with fill "forward"
  When the request is processed
  Then the response status is 422
  And the error identifies "fill" as the invalid parameter

Scenario: Observed-only mode never labels a filled price as an observation
  Given the data source has observations on only 2 of the 5 business days in a range
  When a consumer requests that range with fill "none"
  Then every entry in the response corresponds to a date present in the raw source, cache, or fallback file
  And the response contains exactly 2 entries
```

---

### User Story 2 - Known Observation Window Reported on Every Response (Priority: P2)

A consumer needs to know how much real history the service has for an instrument before deciding whether a risk window is viable — for example, rejecting a VaR calculation for a security with only three months of observed history. Both history modes now report the earliest and latest dates for which the service knows of a real observation for that instrument, so the consumer can size its lookback window and detect short-history securities without probing with trial requests.

**Why this priority**: It makes the observed-only series interpretable (a short series could mean a short request or a short-lived instrument), but observed-only history is already useful without it.

**Independent Test**: Request history for an instrument whose known observations start after the requested start date, and assert the reported first observed date matches the instrument's earliest known observation rather than the requested start date. Testable in both fill modes independently of the negative-cache work.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Observation window reported in observed-only mode
  Given the service knows observations for a security from 2024-03-01 to 2025-06-30
  When a consumer requests price history from 2025-01-02 to 2025-01-31 with fill "none"
  Then the response reports first observed date 2024-03-01
  And the response reports last observed date 2025-06-30

Scenario: Observation window reported in default gap-filled mode
  Given the service knows observations for a security from 2024-03-01 to 2025-06-30
  When a consumer requests price history from 2025-01-02 to 2025-01-31 with no fill parameter
  Then the response still contains the full gap-filled business-day series
  And the response reports first observed date 2024-03-01
  And the response reports last observed date 2025-06-30

Scenario: Observation window reflects the instrument, not the requested range
  Given the service knows observations for a security from 2024-03-01 to 2025-06-30
  When a consumer requests price history from 2025-05-01 to 2025-05-31
  Then the reported first observed date is earlier than the requested start date
  And the reported last observed date is later than the requested end date

Scenario: Observation window widens after a request extends the known history
  Given the service knows observations for a security from 2024-03-01 to 2025-06-30
  When a consumer requests price history from 2023-01-02 to 2023-12-29
  And the data source returns observations starting 2023-02-15
  Then the response reports first observed date 2023-02-15
  And a subsequent request for 2025-01-02 to 2025-01-31 also reports first observed date 2023-02-15

Scenario: Observation window is reported for a local-only fallback instrument
  Given a local-only fallback file for an instrument contains rows from 2022-01-03 to 2024-12-31
  When a consumer requests price history for that instrument with fill "none"
  Then the response reports first observed date 2022-01-03
  And the response reports last observed date 2024-12-31

Scenario: Observation window is reported when the fallback file was triggered by an empty primary source
  Given a fallback file for an instrument contains rows from 2022-01-03 to 2024-12-31
  And the entry is not marked local-only
  And the primary data source returns no observations for that instrument
  When a consumer requests price history for that instrument
  Then the response reports first observed date 2022-01-03
  And the response reports last observed date 2024-12-31

Scenario: Existing response fields are unchanged by the additive window fields
  Given a consumer requests price history for a security
  When the response is returned
  Then the response contains the ticker, currency and prices fields exactly as before this feature
  And each price entry contains only the date, close and fx_rate fields
  And the two observation window fields are present in addition to those
```

---

### User Story 3 - Remember That No History Exists Before the Earliest Observation (Priority: P2)

A consumer repeatedly asks for a long lookback window — for example, five years of daily history for a VaR calculation — for a security that only started trading two years ago. The first such request discovers that the data source has nothing before the earliest observation. Today every later request repeats that same fruitless call to the data source, making each request slow and wasteful. The service now remembers that no data exists before the earliest known observation for that instrument and serves later requests for the same empty segment from what it already holds, without calling the data source. If a later fetch does turn up earlier data, that memory is discarded so the service does not wrongly suppress real history.

**Why this priority**: It turns a repeated multi-second cost into a one-off cost for exactly the long-lookback request pattern VaR depends on. Important, but the feature's correctness value lives in Story 1.

**Independent Test**: Request history starting before the earliest known observation twice in succession with the data source instrumented, and assert the data source is called for the earlier segment on the first request only, with the suppression recorded in the logs.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Empty earlier segment is fetched once and remembered
  Given the service holds observations for a security from 2024-01-02 onwards
  And the data source has no observations before 2024-01-02
  When a consumer requests price history from 2023-01-02 to 2024-06-30
  Then the data source is called for the segment before 2024-01-02
  And the service records that no data exists before 2024-01-02
  When the same consumer repeats the request for 2023-01-02 to 2024-06-30
  Then the data source is not called for the segment before 2024-01-02
  And the response contains the same price entries as the first request

Scenario: A request starting even earlier is also served without a data source call
  Given the service has recorded that no data exists before 2024-01-02 for a security
  When a consumer requests price history from 2020-01-02 to 2024-06-30
  Then the data source is not called for any segment before 2024-01-02
  And the response contains only entries from 2024-01-02 onwards

Scenario: Suppression of a known-empty segment is visible in the logs
  Given the service has recorded that no data exists before 2024-01-02 for a security
  When a consumer requests price history starting before 2024-01-02
  Then a log entry records that the earlier segment fetch was skipped
  And the log entry identifies the instrument and the skipped segment boundary

Scenario: Recording a newly discovered empty segment is visible in the logs
  Given the service holds observations for a security from 2024-01-02 onwards
  And the data source has no observations before 2024-01-02
  When a consumer requests price history starting before 2024-01-02
  Then a log entry records that no earlier data exists for the instrument before 2024-01-02

Scenario: Memory is invalidated when earlier data is later discovered
  Given the service has recorded that no data exists before 2024-01-02 for a security
  And the stored history for that security is cleared
  When a consumer requests price history from 2023-01-02 to 2024-06-30
  And the data source returns observations starting 2023-03-01
  Then the response contains entries from 2023-03-01 onwards
  And the recorded no-earlier-data boundary is updated to 2023-03-01
  And a log entry records that the previous no-earlier-data record was invalidated

Scenario: Remembered empty segment does not suppress fetching a later segment
  Given the service has recorded that no data exists before 2024-01-02 for a security
  And the service holds observations up to 2024-06-30
  When a consumer requests price history from 2023-01-02 to 2025-06-30
  Then the data source is called for the segment after 2024-06-30
  And the data source is not called for the segment before 2024-01-02

Scenario: Boundary is recorded on the first request, before any history is stored
  Given the service holds no stored history for a security
  When a consumer requests price history from 2023-01-02 to 2025-06-30
  And the data source returns observations beginning 2024-01-02
  Then the service records that no data exists before 2024-01-02
  When the same consumer repeats the request
  Then the data source is not called for the segment before 2024-01-02

Scenario: A data source outage is never recorded as absence of data
  Given the service holds observations for a security from 2024-01-02 onwards
  And the data source is unavailable
  When a consumer requests price history from 2023-01-02 to 2024-06-30
  Then the response status is 503
  And no no-earlier-data boundary is recorded for that security
  When the data source becomes available and returns observations beginning 2023-03-01
  And the consumer repeats the request
  Then the response contains entries from 2023-03-01 onwards
```

---

### User Story 4 - Observed-Only History from Local Fallback Files (Priority: P3)

A consumer requests observed-only history for an instrument the primary data source does not cover, which is served from a configured local price file. The consumer receives exactly the rows present in that file within the requested range, with no business days manufactured by gap-fill — so the same real-versus-filled distinction holds for privately tracked instruments as for exchange-traded ones.

**Why this priority**: Local fallback instruments are a minority of the portfolio but would silently produce wrong VaR inputs if they ignored the new mode. Consistency matters; volume is low.

**Independent Test**: Configure a local-only fallback file with observations on a subset of business days, request observed-only history across that range, and assert the response contains exactly the file's rows in range and nothing else.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Observed-only history returns the fallback file's raw rows in range
  Given a local-only fallback file for an instrument contains rows for 2025-01-02, 2025-01-06 and 2025-01-09
  When a consumer requests price history for that instrument from 2025-01-02 to 2025-01-09 with fill "none"
  Then the response contains exactly 3 price entries
  And the entries are for 2025-01-02, 2025-01-06 and 2025-01-09

Scenario: Fallback file rows outside the requested range are excluded
  Given a local-only fallback file for an instrument contains rows for 2024-12-31, 2025-01-06 and 2025-01-20
  When a consumer requests price history from 2025-01-02 to 2025-01-09 with fill "none"
  Then the response contains exactly 1 price entry for 2025-01-06

Scenario: Default mode still gap-fills fallback file data
  Given a local-only fallback file for an instrument contains rows for 2025-01-02 and 2025-01-09
  When a consumer requests price history from 2025-01-02 to 2025-01-09 with no fill parameter
  Then the response contains an entry for every business day from 2025-01-02 to 2025-01-09
```

---

### User Story 5 - Currency-Converted Observed-Only History (Priority: P3)

A consumer holding a foreign-denominated security requests observed-only history in its reporting currency. Each observed price is converted at that date's exchange rate, so the returned series carries only real price observations expressed in the requested currency, with no manufactured price dates introduced by the conversion step.

**Why this priority**: Needed for correct VaR on non-GBP holdings, but it builds directly on Story 1 and adds no value before it exists.

**Independent Test**: Request observed-only history with a target currency for a security with observations on a subset of business days, and assert the response contains only the observed dates, each converted at that date's rate.

**Acceptance Scenarios** *(MANDATORY — Gherkin format)*:

```gherkin
Scenario: Observed-only prices converted at each observation's own date rate
  Given a security quoted in USD has observations on 2025-01-02 and 2025-01-06 only
  And the exchange rate for 2025-01-02 differs from the rate for 2025-01-06
  When a consumer requests that range in GBP with fill "none"
  Then the response currency is GBP
  And the response contains exactly 2 price entries
  And each entry's price reflects the exchange rate for its own date

Scenario: A missing exchange rate on an observation date does not drop the observation
  Given a security quoted in USD has an observation on a date where the exchange rate source has no rate
  When a consumer requests that range in GBP with fill "none"
  Then the response still contains an entry for that observation date
  And the price is converted using the gap-filled exchange rate carried into that date

Scenario: Currency conversion does not reintroduce non-observed dates
  Given a security quoted in USD has observations on 2 of the 5 business days in a range
  And the exchange rate source has rates for all 5 business days
  When a consumer requests that range in GBP with fill "none"
  Then the response contains exactly 2 price entries
```

---

### Edge Cases

- **No observations at all in the requested range, observed-only mode**: the service returns a not-found response, consistent with the existing gap-filled behaviour, rather than a success response with an empty price list.
- **Exactly one observation in the requested range, observed-only mode**: the response contains that single entry. No fill is applied to extend it, and the response is a success (the consumer decides whether one point is enough for its calculation).
- **Weekend observations**: if the source, cache, or fallback file holds an observation dated on a Saturday or Sunday, observed-only mode returns it, because it is a real observation. Gap-filled mode continues to exclude weekend dates as it does today.
- **Requested range entirely before the earliest known observation**: observed-only mode returns a not-found response, and the request contributes to (or is served by) the remembered no-earlier-data boundary rather than repeatedly calling the data source.
- **Requested end date in the future**: observed-only mode simply has no observations for future dates, so the series ends at the latest real observation; the reported last observed date is unaffected by the request's end date.
- **Instrument quoted in minor units (pence)**: the existing minor-unit normalisation applies identically in both fill modes, so observed prices are returned in major units as they are today.
- **Stored history cleared between requests**: both the observation window and the remembered no-earlier-data boundary are re-derived from whatever the next fetch returns, with no stale suppression surviving the clear.
- **Concurrent requests discovering different history boundaries**: the recorded boundary converges on the earliest observation actually seen; a request that discovers earlier data always wins over a record claiming nothing exists earlier.
- **Existing consumers that ignore the new response fields**: the two new fields are additive and the default price list is byte-for-byte what it is today, so no existing consumer is affected.

---

## Requirements *(mandatory)*

### Functional Requirements

> **On the four observed-only requirements (FR-005 to FR-008)**: these overlap by design, not by accident. FR-005 defines what the response must contain, FR-006 forbids the specific mechanisms that would violate it, FR-007 governs the fidelity of each returned value, and FR-008 states the outcome that must never occur regardless of how it might arise. Each is independently testable, which is why they are kept separate rather than merged into one broad requirement.

#### Fill mode selection

- **FR-001**: The security price history endpoint MUST accept an optional request parameter named `fill` with exactly two permitted values: `all` and `none`. (The endpoint's path parameter is named `ticker` in the published contract, and accepts a resolved ticker or any key configured in the local fallback configuration — including an ISIN, CUSIP or SEDOL. The feature description's `{identifier}` and the contract's `{ticker}` refer to the same parameter.)
- **FR-002**: When `fill` is omitted, the service MUST behave as `fill=all`, producing a price list identical to the behaviour before this feature — with one deliberate exception: a requested range containing no observations now returns a not-found response rather than a success response with an empty price list, per FR-009. This is the only non-additive change in this feature.
- **FR-003**: When `fill=all` is supplied explicitly, the returned price list MUST be identical to the list returned when `fill` is omitted for the same request.
- **FR-004**: When `fill` is supplied with any value other than `all` or `none`, the service MUST reject the request with a validation error naming the `fill` parameter, and MUST NOT call the data source.
- **FR-005**: When `fill=none` is supplied, the response MUST contain an entry for every date within the requested range that has a real observation from the primary data source, the local cache, or a configured local fallback file, and MUST contain no entry for any other date.
- **FR-006**: When `fill=none` is supplied, the service MUST NOT apply forward-fill, back-fill, end-of-range fill, or business-day grid generation to the price series.
- **FR-007**: A price entry returned under `fill=none` MUST carry the observed value for that date exactly as sourced, subject only to the existing minor-unit normalisation and any requested currency conversion.
- **FR-008**: Under `fill=none`, the service MUST NOT present a filled value as an observation under any circumstance, including when the underlying store already holds previously filled values.
- **FR-009**: When the requested range contains no observations, the service MUST return a not-found response in both fill modes.
- **FR-010**: The `fill` parameter MUST apply only to the security price history endpoint. The current-price endpoint and the FX pair history endpoint MUST be unchanged by this feature: supplying `fill` to either of them MUST have no effect on the response they return. The parameter is not required to be rejected there — ignoring an unrecognised query parameter is the service's existing behaviour, and "unchanged" means exactly that.

#### Observation window reporting

- **FR-011**: The security price history response MUST include a field reporting the earliest date for which the service knows of a real observation for the instrument, and a field reporting the latest such date.
- **FR-012**: These two fields MUST be populated in both fill modes.
- **FR-013**: These two fields MUST describe the instrument's known observation window, independent of the requested start and end dates — they MUST NOT be clipped to the requested range.
- **FR-014**: These two fields MUST be derived from real observations only, never from filled values.
- **FR-015**: When a request causes the service to learn of observations outside its previously known window, the response MUST report the widened window, and later requests MUST continue to report the widened window.
- **FR-016**: The two new response fields MUST be additive: all existing response fields and the existing price list format MUST remain unchanged, so existing consumers continue to work without modification.
- **FR-017**: Whenever a local fallback file served the request, the reported window MUST reflect the earliest and latest rows the service has read from that file. This applies both to an instrument configured as local-only and to one where the file was used because the primary data source returned no observations — the window MUST follow whichever source actually supplied the prices, not the instrument's configuration.

#### Remembering empty earlier segments

- **FR-018**: When a request asks for history starting before the earliest stored observation for an instrument and the data source returns no observations for that earlier segment, the service MUST record that no data exists for that instrument before its earliest observation.
- **FR-019**: When a later request's range starts earlier than the instrument's earliest stored observation, and a recorded boundary asserts that no data exists before that earliest stored observation, the service MUST NOT call the data source for the segment preceding it. A request starting on or after the earliest stored observation has no earlier segment to fetch, so the boundary does not arise.
- **FR-020**: Suppressing an earlier-segment fetch MUST NOT affect the request's other segments: a segment after the latest stored observation MUST still be fetched as it is today.
- **FR-021**: Suppressing an earlier-segment fetch MUST NOT change the price entries the consumer receives compared with an unsuppressed request for the same range.
- **FR-022**: When a fetch returns observations earlier than a recorded no-earlier-data boundary, the service MUST discard or move that boundary to the newly discovered earliest observation, so real history is never suppressed.
- **FR-023**: The recorded boundary MUST survive service restarts for as long as the stored history it refers to survives, and MUST be discarded when that stored history is deleted.
- **FR-024**: The service MUST write a log entry when it records a new no-earlier-data boundary, when it skips an earlier-segment fetch because of one, and when it invalidates one. Each entry MUST identify the instrument and the relevant date boundary.
- **FR-027**: When the service holds no stored history for an instrument and a request's fetch returns observations beginning after the requested start date, the service MUST record that no data exists before that first returned observation. The data source was asked for the whole requested range and returned nothing earlier, so the same inference applies as in FR-018. Without this, the first long-lookback request — the one that populates the store and pays the full cost — leaves no record, and the saving does not arrive until a third request.
- **FR-028**: The service MUST NOT record a no-earlier-data boundary on the basis of a data source error. Only a successful response that contained no observations for the segment is evidence that data does not exist; an unavailable or failing data source MUST leave any existing boundary untouched and MUST NOT create one. Misrecording an outage would permanently suppress real history for that instrument.

#### Currency conversion under observed-only mode

- **FR-025**: When currency conversion is requested with `fill=none`, the service MUST convert each observed price using the gap-filled exchange rate for that observation's own date, matching today's conversion behaviour.
- **FR-026**: Currency conversion under `fill=none` MUST NOT add entries for dates that have no price observation, and MUST NOT drop an observation because the exchange rate source lacks a raw rate for that date.

### Key Entities

- **ObservedPriceSeries**: The set of (date, price) entries for an instrument that correspond to real observations from the primary data source, the local cache, or a configured local fallback file, restricted to the requested date range. Contains no manufactured dates.
- **ObservationWindow**: The earliest and latest dates for which the service knows of a real observation for an instrument, derived from everything the service currently holds or has just fetched. Widens as more history is discovered; never derived from filled values.
- **NoEarlierDataBoundary**: A record, held per instrument alongside its stored history, asserting that the data source has no observations before a given date. Consulted to skip repeat fetches of a known-empty earlier segment; invalidated when earlier observations are discovered or the stored history is removed.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any instrument and date range, an observed-only history response contains zero dates that are not present in the underlying source, cache, or fallback file — verifiable by comparing the response dates against the stored observations.
- **SC-002**: A return distribution computed from an observed-only series over a range containing public holidays contains no zero-return days attributable to non-trading dates, whereas the same range in default mode does.
- **SC-003**: Every existing security price history request made without the new parameter returns the same price list it returned before this feature, confirmed by the existing test suite passing unchanged.
- **SC-004**: Both history modes report an earliest and latest known observation date on every successful response, and those dates match the instrument's stored observation extremes in 100% of checked cases.
- **SC-005**: A long-lookback request that extends before an instrument's earliest observation calls the data source for the empty earlier segment at most once per instrument, with later identical requests calling it zero times.
- **SC-006**: Repeating a five-year lookback request for a two-year-old instrument completes in no more than 50% of the first attempt's elapsed time, measured end to end against a running service. 50% is a deliberately conservative floor — the second request makes no data-source call at all, so the real saving is expected to be far larger; the threshold exists so the criterion is pass/fail rather than a matter of opinion.
- **SC-007**: Recording, skipping, and invalidating a no-earlier-data boundary are each traceable in the service logs with the instrument and date boundary identified.
- **SC-008**: An observed-only series requested in a non-quote currency contains the same set of dates as the same request in the quote currency, with each price converted at its own date's rate.
- **SC-009**: A consumer can determine, from a single history response, whether the service holds enough real history for a required risk lookback window, without issuing exploratory requests.

---

## Assumptions

- The `fill` parameter is an enumeration with exactly two values for now. `all` and `none` are the only permitted values; no partial or directional fill modes (for example forward-only) are in scope.
- `fill=all` is the default specifically to preserve backward compatibility for every existing consumer; no existing caller is expected to change.
- The new response fields are named `first_observed_date` and `last_observed_date`, matching the consumer's expectation stated in the request.
- "As far as the service knows" means the union of what the service currently holds for the instrument and what the current request just fetched — the service does not probe the data source for the instrument's full lifetime in order to populate these fields.
- A range with no observations returns not-found in both fill modes rather than a success response with an empty list. This aligns the service with its already-published contract (feature 006's FR-008), which the current code does **not** honour in one path: when a cached instrument is queried over a range its cache holds no rows for, the service today answers 200 with an empty price list. Observed-only mode makes that path common, so the gap is closed rather than retained. See FR-002 and FR-009.
- The existing minor-unit (pence) normalisation and identifier resolution behaviour apply unchanged in both fill modes.
- Gap-filled exchange rates remain the conversion input in both fill modes, as established by the price-series-fill feature: a filled rate is preferable to dropping or zeroing a real price observation.
- The no-earlier-data boundary is stored alongside the instrument's existing stored history, so deleting that stored history also removes the boundary. Clearing all stored history clears all boundaries.
- The no-earlier-data mechanism applies only to segments before the earliest observation. Segments after the latest observation continue to be fetched on every request, because new data legitimately arrives there.
- The no-earlier-data mechanism applies to instruments served from the primary data source. Local-only fallback instruments never call the data source, so the mechanism is irrelevant to them.
- The consumer of this feature is the Value-at-Risk calculation in the portfolio analysis service; this specification covers only the market data service side of that work.
- Authentication and authorisation requirements are unchanged from existing endpoints (none, for this local deployment).
