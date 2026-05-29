# Feature Specification: Price Series Gap Fill

**Feature Branch**: `006-price-series-fill`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "Not all time series returned from YFinance will be populated for all dates, especially around market holidays but also due to missing or incomplete data. The API for current and historical data should return a price for every business date (Mon-Fri) in the requested date range. There should be a post-processing step after raw data (inc. cached copies) is validated and gaps filled in before being returned to the client. In the situation where there are gaps within the time series a 'forward fill' algorithm should copy the most recent, previous price forward until a new market observation is available. In the case that the first observed price is after the start date of a historical request then a back-fill operation should copy the first observed price back to the start of the requested window. This filling logic should occur on the raw data from the API and/or cache and prior to any FX conversion. This will be apparent in any periods of flat-filled prices that may still exhibit day-to-day moves due to currency fluctuations. Another edge case here is where the requested date is 'today' and the underlying datasource (YFinance) has the most recent observation only for T-1 or T-2 business dates; this logic should ensure that the most recent observation still results in a value for today if that was requested."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Forward-Fill Price Gaps Within History (Priority: P1)

A client requests a price history for a date range. Some business days within that range (Mon–Fri) have no market observation — for example, a public holiday falls mid-week, or the data source has a temporary gap. Instead of returning a series with missing entries, the service returns a price for every business day by carrying the most recent available price forward until a new observation is available. The client receives a complete, contiguous series covering the full requested range.

**Why this priority**: This is the core value of the feature. Without forward-fill, clients building performance charts, return calculations, or time-weighted returns will see missing data for holidays and data outages, forcing them to handle gaps themselves. Every downstream analysis depends on a complete series.

**Independent Test**: Can be fully tested by requesting history for a date range known to contain a mid-week market holiday, asserting that the response contains entries for every Mon–Fri in the range and that the holiday entry carries the same price as the preceding trading day. Delivers immediate value as a standalone capability.

**Acceptance Scenarios**:

```gherkin
Scenario: Mid-series gap is filled by forward-fill
  Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
  And 2025-01-03 is a market holiday with no observation
  When a client requests price history from 2025-01-02 to 2025-01-06
  Then the response contains 3 entries (2025-01-02, 2025-01-03, 2025-01-06)
  And the entry for 2025-01-03 has the same price as 2025-01-02 (100.00)
  And the entry for 2025-01-06 has price 102.00

Scenario: Multiple consecutive gaps are all forward-filled
  Given the data source has a price for 2025-01-02 at 100.00 and 2025-01-07 at 105.00
  And 2025-01-03, 2025-01-06 have no observations (holiday block)
  When a client requests price history from 2025-01-02 to 2025-01-07
  Then the response contains 4 entries (2025-01-02, 2025-01-03, 2025-01-06, 2025-01-07)
  And the entries for 2025-01-03 and 2025-01-06 both carry price 100.00

Scenario: End-of-range gap is filled forward to requested end date
  Given the data source has prices up to 2025-01-03 (Friday)
  And the next observation is not available until 2025-01-08 (Wednesday)
  When a client requests price history from 2025-01-02 to 2025-01-07 (Tuesday)
  Then the response contains entries for every business day 2025-01-02 through 2025-01-07
  And entries for 2025-01-06 and 2025-01-07 carry the price from 2025-01-03
```

---

### User Story 2 — Back-Fill from Requested Start Date (Priority: P2)

A client requests price history starting from a date before the first available market observation — for example, a request starting on a Monday when the data source's first observation is Wednesday (because Monday and Tuesday are public holidays or the security was not yet traded). Instead of returning a truncated series starting at Wednesday, the service fills prices backward from the first observation to the requested start date.

**Why this priority**: Clients who request fixed-length windows (e.g., "the last 30 days") expect results from day 1. Without back-fill, analysis windows are silently shorter than requested, distorting time-weighted returns and comparisons between securities.

**Independent Test**: Can be fully tested independently by submitting a request whose start date precedes the first available observation and asserting that every business day from the start date to the first observation carries the first observed price.

**Acceptance Scenarios**:

```gherkin
Scenario: Start of range precedes first observation — back-fill applied
  Given the data source has no price for 2025-01-02 or 2025-01-03
  And the first available price is 2025-01-06 at 100.00
  When a client requests price history from 2025-01-02 to 2025-01-07
  Then the response contains entries for every business day 2025-01-02 through 2025-01-07
  And the entries for 2025-01-02 and 2025-01-03 carry price 100.00 (back-filled from 2025-01-06)
```

---

### User Story 3 — Fill Forward to Today When Source Data Is Stale (Priority: P3)

A client requests price history with an end date of today. The data source's most recent observation is from one or two business days ago (for example, because today's market has not yet closed, or due to a data delivery lag). The service forward-fills from the last known observation to today so the client receives a price for today in the response.

**Why this priority**: Clients requesting "up to today" need a current price anchor for end-of-day reports and dashboards. Without this, a request ending today would silently truncate to the last available trading day, leaving today absent from the series.

**Independent Test**: Can be fully tested by requesting history with an end date of today when the data source returns observations only up to yesterday. The response must include an entry for today carrying yesterday's price.

**Acceptance Scenarios**:

```gherkin
Scenario: Data source only has observation for yesterday — today is forward-filled
  Given today is a business day
  And the data source has a price for yesterday (T-1) at 100.00 but no price for today
  When a client requests price history ending today
  Then the response contains an entry for today
  And the entry for today carries yesterday's price (100.00)

Scenario: Data source observation is two business days old — T-2 fills to today
  Given today is a business day
  And the data source has a price for T-2 at 100.00 but no observations for T-1 or today
  When a client requests price history ending today
  Then the response contains entries for T-1 and today
  And both entries carry the T-2 price (100.00)
```

---

### Edge Cases

- What if the data source returns no observations at all for the requested range? The service returns an empty series (no gap-fill can be applied without at least one anchor price) and returns a 404.
- What if the requested start date is a weekend? Weekend days (Sat/Sun) are excluded from the business-day series — the gap-fill logic only generates entries for Mon–Fri.
- What if the requested end date is in the future? Gap-fill will forward the last known price to the requested end date, treating future business days identically to today with no observation.
- What happens when gap-filled prices are combined with FX conversion? Gap-fill runs on the raw price series first. FX rates are then applied per date in the filled series. This means that a gap-filled entry (carrying a repeated price) will receive the FX rate for its own date, not the date of the original observation. The resulting currency-converted price may therefore differ day-to-day despite the underlying price being unchanged — this is expected and correct behaviour.
- What if the range contains only weekends (e.g., start Saturday, end Sunday)? The response contains zero entries; no gap-fill is applied.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For historical price requests (securities and FX pairs), the service MUST return a price or rate entry for every business day (Mon–Fri) within the requested start-to-end date range, inclusive.
- **FR-002**: When a business day has no market observation, the service MUST carry the most recent prior observation's price forward to fill that business day (forward-fill).
- **FR-003**: When the first available market observation is after the requested start date, the service MUST copy that first observation's price back to all business days between the requested start date and the first observation (back-fill).
- **FR-004**: When the requested end date has no observation and the data source's most recent observation predates the end date, the service MUST forward-fill from the last observation to the requested end date.
- **FR-005**: Gap-fill MUST be applied to the raw security price series (from both live data source and cached data) before any currency conversion is performed.
- **FR-006**: Gap-fill MUST NOT alter or remove existing market observations — only missing business days receive filled values.
- **FR-007**: Weekend days (Sat/Sun) MUST NOT appear in the returned price or rate series regardless of the requested date range.
- **FR-008**: If the raw price series contains no observations at all for the requested range, the service MUST return a not-found response rather than an empty filled series.
- **FR-009**: The FX pair history endpoint MUST apply the same gap-fill logic (forward-fill, back-fill, end-of-range fill) as the security price history endpoint, returning a rate for every business day in the requested range.
- **FR-010**: When performing currency conversion on a security price series, the service MUST use the gap-filled FX rate series (not the raw FX rates) so that no missing FX rate can introduce artificial spikes, jumps, or zero values into the converted price series.

### Key Entities

- **BusinessDaySeries**: An ordered, contiguous sequence of (date, value) entries covering every Mon–Fri in a requested date range. The authoritative output of gap-fill processing; applies to both security prices and FX rates.
- **MarketObservation**: A (date, price) pair sourced directly from the data provider or cache for a specific trading day. The only input to gap-fill for security price series.
- **FXRateObservation**: A (date, rate) pair sourced directly from the data provider or cache for a specific trading day. The only input to gap-fill for FX rate series.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of business days (Mon–Fri) within any historical price request contain a price entry in the response — no gaps for holidays, data outages, or end-of-range staleness.
- **SC-002**: A request spanning a known 4-day public holiday block (e.g., Easter or Christmas) returns the holiday entries carrying the last pre-holiday price, with the post-holiday entry reflecting the new market observation.
- **SC-003**: A request ending on today's date always returns an entry for today, even when the data source's most recent observation is from T-1 or T-2.
- **SC-004**: When currency translation is applied to a series containing gap-filled security price entries, each filled entry's price reflects the FX rate for that specific business day (not the FX rate of the original observation date), demonstrating that gap-fill precedes FX conversion.
- **SC-005**: A currency-converted security price series contains no artificial spikes or zero-value entries attributable to missing FX rates — the gap-filled FX rate series is used as the conversion input, producing a smooth series even when the underlying FX data source has gaps on the same days as the security price gaps.

---

## Assumptions

- Business days are defined strictly as Mon–Fri. Market-specific public holiday calendars are not consulted; the service generates a Mon–Fri business day grid and fills any date within that grid that lacks an observation.
- The back-fill anchor is always the first available market observation (not a synthetic or default price).
- The forward-fill anchor is always the most recent prior market observation available (not a forecast or interpolated value).
- Gap-fill applies to the security price history endpoint and the FX pair history endpoint. The current-price endpoint's existing behaviour (returning the most recent available observation) is unchanged by this feature.
- When converting security prices to a different currency, gap-filled FX rates are used as the conversion input. This ensures a missing FX rate on any given business day cannot introduce an artificial spike, jump, or zero in the converted price series. The design principle is: flat-filled data that is reasonably correct is preferable to missing or zero entries.
- The end date for gap-fill purposes is the requested end date — future dates beyond today are treated identically to today (no observation available, so they are forward-filled from the last known price).
- Authentication and authorisation requirements are the same as existing endpoints (none, for this local deployment).
- The gap-fill behaviour does not need to be switchable per request; it is always applied.
- Gap-filled price entries are not distinguishable from observed market prices in the API response. All entries are returned in the same format; no additional field is added to indicate fill status.

---

## Clarifications

### Session 2026-05-15

- Q: Should the API response include a per-entry indicator distinguishing gap-filled prices from observed market prices? → A: No — all entries use the same response format; no `is_filled` or `fill_type` field is added. The response model is unchanged.
- Q: Does gap-fill apply to the FX pair history endpoint, or only to security price history? → A: Both — gap-fill applies to security price history and FX pair history endpoints. Additionally, gap-filled FX rates (not raw FX rates) MUST be used internally when performing currency conversion of security prices, so that missing FX data cannot introduce artificial spikes or jumps. Design principle: flat-filled data that is reasonably correct is preferable to missing or zero entries.
