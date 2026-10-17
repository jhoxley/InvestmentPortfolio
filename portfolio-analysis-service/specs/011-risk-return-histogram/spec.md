# Feature Specification: Risk Endpoints — Daily Return Histogram

**Feature Branch**: `011-risk-return-histogram`
**Created**: 2026-09-26
**Status**: Draft
**Input**: User description: "Create a new set of endpoints on the portfolio-analysis-service under a controller called 'risk'. The first of these is to build up a histogram response for a given date range of portfolio-level daily returns. The data here should be the same input data as for the 'performance' endpoints and should share implementation code where feasible. Given a start date and end date input parameter, the calculation should retrieve all daily returns at the portfolio level (sum of weighted_position_return of each position/sub-account per date), convert them to basis points (1 basis point = 1/100th of 1%, or 1/10000) and then count observations over the time frame per basis point bucket. Round to the nearest, integer basis point. The API response should have one part as a list of pairs, where the key is the basis point bucket and the value is the number of dates where the daily return matched that number of basis points. Buckets with zero observations are not included. The response should sort from smallest basis point bucket to largest. An additional section of the response should return statistics for the same distribution - mean, median, mode, standard deviation (1 standard deviation, 2 standard deviations and 3 standard deviations), count of observations, skewness, kurtosis, minimum and maximum."

## Clarifications

### Session 2026-09-26

- Q: How should the 1, 2 and 3 standard deviation statistics be returned? → A: For each k in 1, 2, 3, return both the σ multiple (k × standard deviation) and the band edges (mean − kσ and mean + kσ), all in basis points.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve a Daily Return Histogram for an Account (Priority: P1)

A developer building a risk view (e.g. a return-distribution chart in a Dash App) requests, for an
account and a start/end date range, the distribution of the account's portfolio-level daily returns
expressed in whole basis points. The response lists each basis point bucket that had at least one
observation together with the number of business days whose return fell in that bucket, ordered from
the most negative bucket to the most positive.

**Why this priority**: The histogram is the core deliverable of the feature and the first endpoint of
the new risk group; without it there is nothing for a risk chart to draw.

**Independent Test**: For an account with a known set of daily portfolio returns in a date range,
request the histogram and verify each bucket's count equals the number of days whose return, converted
to basis points and rounded to the nearest integer, equals that bucket, that empty buckets are absent,
and that buckets are sorted ascending.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Daily returns are bucketed by rounded basis points
  Given account "test-portfolio" has daily portfolio returns of 0.0010, 0.00104, 0.0011, -0.0025
      and 0.0010 across five business days in the requested range
  When the histogram is requested for that range
  Then the buckets are [(-25, 1), (10, 3), (11, 1)]

Scenario: Buckets with no observations are omitted
  Given daily portfolio returns that round to -5 bps and +5 bps only
  When the histogram is requested
  Then the response contains only the buckets -5 and 5, with no entries for -4 through 4

Scenario: Buckets are sorted from smallest to largest
  Given daily portfolio returns that round to 12, -3, 0 and 7 basis points
  When the histogram is requested
  Then the buckets appear in the order -3, 0, 7, 12

Scenario: Portfolio-level daily return is the sum of weighted position returns
  Given on 2024-03-04 sub-accounts "Equities A" and "Equities B" have weighted_position_return
      0.011 and -0.0045
  When the histogram is requested for a range including 2024-03-04
  Then that date contributes one observation to the 65 basis point bucket
```

---

### User Story 2 - Distribution Statistics Alongside the Histogram (Priority: P1)

The same response carries a statistics section summarising the distribution of the same observations:
mean, median, mode, standard deviation at 1, 2 and 3 standard deviations, count of observations,
skewness, kurtosis, minimum and maximum — so a caller can annotate the chart (e.g. draw ±1σ/2σ/3σ
bands) and assess tail risk without recomputing anything.

**Why this priority**: The histogram alone shows shape; the statistics turn it into a usable risk
measure. Both are requested as one response.

**Independent Test**: For a small hand-computable set of daily returns, verify every statistic in the
response against values calculated independently.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Statistics describe the same observations as the histogram
  Given daily portfolio returns that round to -10, 0, 0, 10 and 20 basis points
  When the histogram is requested
  Then the statistics report count 5, minimum -10, maximum 20, mean 4, median 0 and mode 0
  And for each of 1, 2 and 3 standard deviations the statistics give the multiple (1x, 2x, 3x the
      sample standard deviation) and the band edges (mean minus and mean plus that multiple)

Scenario: Count matches the histogram
  Given any valid request that returns a histogram
  Then the statistics count equals the sum of all bucket counts
```

---

### User Story 3 - Shared Data Source and Date Handling with Performance (Priority: P2)

A maintainer expects the histogram to be derived from exactly the same portfolio-level daily return
series that the performance endpoints use, and to accept and validate the same account and date
inputs, so the two groups of endpoints can never disagree about what an account's daily return was.

**Why this priority**: Consistency and reuse rather than new user-visible capability, but it prevents
divergent numbers between performance and risk views.

**Independent Test**: For the same account and date, verify the daily return feeding the histogram
equals the daily return feeding the performance measures.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Histogram and performance use the same daily returns
  Given account "test-portfolio" with ingested position data
  When the histogram is requested for 2024-01-02 to 2024-06-28
  Then the total observation count equals the number of business days in that range for which the
      performance endpoints have a daily portfolio return
```

---

### User Story 4 - Clear Handling of Invalid or Empty Requests (Priority: P2)

A developer who supplies a bad date range, an unknown account, or a range with no data gets a clear
outcome rather than misleading or crashing output.

**Why this priority**: Predictable errors are needed for a dependable API but do not add new analytics.

**Independent Test**: Issue requests with start after end, an unknown account, and a range containing
no returns, and verify each produces the specified outcome.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Start date after end date is rejected
  Given a request with start 2024-06-01 and end 2024-01-01
  When the histogram is requested
  Then the request is rejected with a client error describing the invalid date range

Scenario: Unknown account is reported as not found
  Given no account named "missing" exists
  When the histogram is requested for "missing"
  Then the response is a not-found error, consistent with the performance endpoints

Scenario: Future end date is rejected
  Given a valid account
  When the histogram is requested with an end date later than today
  Then the request is rejected with a client error consistent with the performance endpoints

Scenario: Account without a position ladder is rejected
  Given an account that has only a capital ledger
  When the histogram is requested
  Then the request is rejected with a client error consistent with the performance endpoints

Scenario: Weekend end date follows performance date adjustment
  Given a valid account and an end date that falls on a Saturday earlier than today
  When the histogram is requested
  Then the resolved to_date is the following Monday, matching the performance endpoints

Scenario: Single-day window
  Given a valid account and a start date equal to the end date
  When the histogram is requested
  Then the histogram has exactly one bucket with a count of 1 and the observation count is 1
  And statistics that cannot be computed for one observation (standard deviation, skewness,
      kurtosis) are returned as null rather than causing an error
```

---

### Edge Cases

- Rounding of exact halves (e.g. 0.5 bps): rounded half away from zero, so 0.5 → 1 and -0.5 → -1.
- Returns that round to 0 bps (including tiny positive and negative values) all fall in the 0 bucket.
- A range with a single observation: histogram has one bucket of count 1; standard deviation is null
  (undefined for a sample of one), as are skewness and kurtosis.
- All observations identical: standard deviation is 0 (bands collapse onto the mean); skewness and
  kurtosis are null (undefined).
- Multiple modes (tie for highest count): the smallest tied bucket is reported as the mode.
- Business days with no position data at all: the performance endpoints treat these as a 0.0 daily
  return (never forward-filled); the histogram inherits that behaviour because it shares the same
  daily return series, so such days count as observations in the 0 bp bucket. Weekends are not
  business days and are never observations.
- Empty window: a resolved window always contains at least one business day (start and end are
  business-day aligned with start ≤ end, and the shared series covers every business day from the
  account's first date), so a successful response always has count ≥ 1. The statistics section
  nevertheless defines the zero-observation case (count 0, all other values null) as a defensive
  guarantee.
- Extreme returns (e.g. ±50% in a day) produce large bucket keys; the histogram remains sparse and
  does not pad the gap with empty buckets.
- Start/end omitted: defaults follow the same rules as the performance endpoints.
- Start/end falling on non-business days: dates are adjusted exactly as for the performance
  endpoints — each is moved forward to the next business day (capped at the most recent business
  day on or before today), so a Saturday end date includes the following Monday's return when that
  Monday is not after today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST expose a new "risk" group of endpoints, of which the daily return
  histogram is the first.
- **FR-002**: The histogram endpoint MUST accept an account, a start date and an end date, and follow
  the same account addressing, date-format, defaulting and validation conventions as the performance
  endpoints.
- **FR-003**: The daily return for each business day MUST be the portfolio-level daily return used by
  the performance endpoints, i.e. the sum of `weighted_position_return` across all positions and
  sub-accounts on that date; the two endpoint groups MUST share this computation.
- **FR-004**: Each daily return MUST be converted to basis points (return × 10,000) and rounded to the
  nearest integer basis point (halves rounded away from zero).
- **FR-005**: The response MUST include a histogram section: a list of pairs, each pairing an integer
  basis point bucket with the count of business days in the requested range whose rounded return equals
  that bucket.
- **FR-006**: Buckets with zero observations MUST NOT appear in the histogram.
- **FR-007**: The histogram MUST be sorted by bucket ascending (most negative first).
- **FR-008**: The response MUST include a statistics section, computed over the same observations,
  containing: mean, median, mode, standard deviation at 1, 2 and 3 standard deviations, count of
  observations, skewness, kurtosis, minimum and maximum. For each of k = 1, 2, 3 the standard
  deviation entry MUST provide both the multiple (k × sample standard deviation) and the lower and
  upper band edges (mean − kσ and mean + kσ).
- **FR-009**: All statistics expressed in return units (mean, median, mode, standard deviation
  multiples and band edges, minimum, maximum) MUST be in basis points; count is a plain integer; skewness and kurtosis are
  dimensionless.
- **FR-010**: Statistics that are mathematically undefined for the available observations (e.g.
  sample standard deviation with fewer than 2 observations, skewness with fewer than 3, kurtosis
  with fewer than 4, skewness/kurtosis with zero variance; all statistics for zero observations,
  except count which is 0) MUST be returned as null rather than an error or non-numeric value.
- **FR-011**: The following MUST be rejected with the same problem-details error responses as the
  performance endpoints: an invalid account name; an unknown account (not found); an account with
  no ingested position ladder, or a start date earlier than the ladder's first date; an end date in
  the future; and a start date later than the end date after date adjustment. A valid request with
  no observations is not an error (see FR-010).
- **FR-012**: Only dates within the inclusive requested range contribute observations; no look-back
  beyond the range is applied.
- **FR-013**: The response MUST echo the account, and the resolved start and end dates used.

### Key Entities

- **Portfolio Daily Return**: The account-level return for one business day, equal to the sum of
  weighted position returns for that date; shared with the performance endpoints.
- **Basis Point Bucket**: An integer number of basis points (1 bp = 0.01%) into which a daily return
  is rounded.
- **Histogram Entry**: A pair of (basis point bucket, number of business days in that bucket).
- **Distribution Statistics**: Summary measures (mean, median, mode, standard deviation at 1/2/3
  sigma, count, skewness, kurtosis, minimum, maximum) of the rounded observations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any range, the sum of histogram bucket counts equals the reported observation count
  and equals the number of business days in the range with a portfolio daily return (100% agreement).
- **SC-002**: For a reference data set, every histogram bucket and every statistic matches independently
  calculated values exactly for integers and within 1e-9 relative tolerance for decimals.
- **SC-003**: The daily return for any date used by the histogram is identical to the one used by the
  performance measures in 100% of sampled dates.
- **SC-004**: A caller can obtain the histogram and statistics for a range of up to 10 years of daily
  data in a single request, receiving results in under 2 seconds under normal load.
- **SC-005**: Every invalid request class (bad range, unknown account, missing ladder, future end date) yields a documented,
  predictable outcome with no unhandled failures.

## Assumptions

- The histogram is account-scoped, addressed in the same way as the performance endpoints (account
  identified in the request path), and the risk group is a sibling of the performance group.
- Standard deviation is the sample standard deviation of the rounded basis point observations; the 1, 2
  and 3 standard deviation entries each carry the multiple (1×, 2×, 3× that value) and the band edges
  around the mean.
- Statistics are computed on the rounded integer basis point observations, i.e. the same distribution
  the histogram displays.
- Kurtosis is reported as excess kurtosis (a normal distribution scores 0); skewness is the standard
  sample skewness.
- The daily return series already ingested and used by the performance endpoints is the sole data
  source; no new ingestion is required.
- Further risk endpoints (e.g. value-at-risk, drawdown) are out of scope for this feature and will be
  specified separately.
- Authentication, authorisation and response-envelope conventions follow the existing endpoints.
