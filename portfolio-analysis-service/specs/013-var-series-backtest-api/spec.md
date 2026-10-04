# Feature Specification: VaR Series, Backtest and Methods Endpoints

**Feature Branch**: `013-var-series-backtest-api`
**Created**: 2026-10-04
**Status**: Draft
**Input**: User description: "Add read-only endpoints over the precomputed VaR store from feature 012. GET /v1/accounts/{account}/risk/var returns, for a start/end date range (resolved exactly like the performance endpoints), a look-back (1y, 2y or 5y; default the configured headline 2y) and one or more confidence levels (default all), one entry per business date with the as-of date, the outcome date, total market value, scenario count, coverage percentages, quality flag, and for each confidence level VaR and ES in GBP and as a percentage of total market value, plus the realised hypothetical and ladder PnL on the outcome date and whether each was an exception (loss larger than that level's VaR). If nothing has been computed, return an empty series with links to the status and runs resources rather than an error. GET /v1/accounts/{account}/risk/var/backtest returns, per confidence level over the range: observation count, exception count, expected exceptions, exception rate, Kupiec proportion-of-failures likelihood ratio and p-value, Christoffersen independence and conditional-coverage likelihood ratios and p-values (transition chains break where days are excluded), a traffic-light zone from the binomial distribution (green below 95% cumulative probability, yellow below 99.99%, red otherwise, which reproduces Basel's 0-4/5-9/10+ for 250 days at 99%), exception dates, mean VaR and VaR stability (standard deviation of daily log change in VaR, excluding days when holdings changed); parameters select pnl_basis (hypothetical, the default, or ladder), a minimum quality, and optionally a rolling 250-day exception count series. GET /v1/risk/var/methods describes the available method, look-backs, confidence levels and measures so clients can build controls. No new dependencies: chi-squared p-values via erfc/exp and binomial probabilities via lgamma. Responses follow the existing HATEOAS and RFC 7807 conventions. Methodology reference: docs/proposals/value-at-risk.md section 4."

## User Scenarios & Testing *(mandatory)*

Throughout this section, "the VaR store" is the per-account data built by feature
012's calculation runs (estimates, realised outcomes). These endpoints never trigger a
calculation; they only read what has already been computed.

### User Story 1 - Read an Account's VaR Time Series (Priority: P1)

A developer building a risk chart (daily observed PnL with a VaR overlay) requests, for
an account, a date range and a look-back, the sequence of previously computed VaR/ES
estimates together with what actually happened on each date's outcome day, so the chart
can show both the forecast and the realised result without recomputing anything.

**Why this priority**: This is the core deliverable — the whole reason this feature
exists is to make the already-computed store usable by a client quickly.

**Independent Test**: For an account with a calculation run already completed, request
the series for a known date range and look-back, and verify every returned entry's
values match the stored estimate and outcome exactly, that dates outside the range are
absent, and that an account with nothing computed yet returns an empty series rather
than an error.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: A computed date's series entry matches the stored estimate and outcome
  Given account "var-acct" has a completed VaR run covering 2026-03-02 at look-back "2y"
  When the VaR series is requested for "var-acct" from 2026-03-02 to 2026-03-02 at look-back "2y"
  Then the single returned entry's scenario count, coverage, quality, VaR and ES at every
      confidence level match the stored estimate exactly
  And its hypothetical and ladder PnL match the stored outcome exactly

Scenario: Only the requested look-back's estimates are returned
  Given account "var-acct" has completed estimates at look-backs "1y", "2y" and "5y" for 2026-03-02
  When the VaR series is requested for "var-acct" at look-back "1y"
  Then the returned entry's figures are the "1y" estimate, not "2y" or "5y"

Scenario: Only the requested confidence levels are returned
  Given account "var-acct" has a completed estimate for 2026-03-02 at 95%, 97.5% and 99%
  When the VaR series is requested for "var-acct" with confidence 95% only
  Then the returned entry includes only the 95% VaR/ES figures

Scenario: Omitting confidence returns every configured level
  Given account "var-acct" has a completed estimate for 2026-03-02
  When the VaR series is requested for "var-acct" with no confidence parameter
  Then the returned entry includes every configured confidence level

Scenario: An account with nothing computed returns an empty series, not an error
  Given account "var-acct" has an ingested position ladder but no completed VaR run
  When the VaR series is requested for "var-acct"
  Then the response is 200 with an empty series
  And the response links to the account's VaR status and runs resources

Scenario: An exception flag reflects a loss beyond that confidence level's VaR
  Given a stored estimate for 2026-03-02 with 95% VaR of 1000 GBP
  And the stored outcome's hypothetical PnL for that date is -1200 GBP
  When the VaR series is requested for "var-acct"
  Then that date's 95% entry reports the hypothetical PnL as an exception
```

---

### User Story 2 - Backtest a Confidence Level Against Realised Outcomes (Priority: P1)

A developer or the account owner wants to know, for a chosen confidence level and
look-back, whether the VaR estimates have actually been realistic over a date range:
how often losses exceeded the forecast, whether those exceptions cluster in time, and
how the model would be rated under a standard regulatory-style test.

**Why this priority**: This is the second half of the feature's core value — the series
alone shows forecasts and outcomes side by side, but the backtest is what turns that
into an assessment of whether the model can be trusted.

**Independent Test**: For a small, hand-constructed set of estimates and outcomes with a
known number of exceptions, request the backtest and verify every statistic against an
independently calculated value.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: Exception count matches the number of losses beyond VaR
  Given account "var-acct" has 250 days of 99% VaR estimates and hypothetical outcomes
  And exactly 6 of those days have a loss larger than that day's 99% VaR
  When the backtest is requested for "var-acct" at 99% confidence
  Then the reported observation count is 250 and the exception count is 6

Scenario: The traffic-light zone reproduces the Basel thresholds at 250 days and 99%
  Given account "var-acct" has 250 days of 99% VaR estimates and hypothetical outcomes
  When the exception count is 4
  Then the reported zone is "green"
  When the exception count is 7
  Then the reported zone is "yellow"
  When the exception count is 11
  Then the reported zone is "red"

Scenario: Statistics are computed against hypothetical PnL by default
  Given account "var-acct" has both hypothetical and ladder outcomes stored
  And the two PnL bases disagree on whether 2026-03-10 is an exception
  When the backtest is requested for "var-acct" with no pnl_basis parameter
  Then the exception count reflects the hypothetical PnL basis

Scenario: Requesting the ladder PnL basis changes which days count as exceptions
  Given the same data as the previous scenario
  When the backtest is requested for "var-acct" with pnl_basis "ladder"
  Then the exception count reflects the ladder PnL basis instead

Scenario: A minimum quality filter excludes lower-quality dates from the backtest
  Given account "var-acct" has 10 "ok" days, 5 "degraded" days and 3 "insufficient" days
      in the requested range at the requested look-back
  When the backtest is requested for "var-acct" with a minimum quality of "ok"
  Then the reported observation count is 10

Scenario: Insufficient-quality dates are always excluded, even without a filter
  Given account "var-acct" has 10 "ok" days and 3 "insufficient" days (no stored VaR value)
      in the requested range
  When the backtest is requested for "var-acct" with no minimum quality parameter
  Then the reported observation count is 10, not 13

Scenario: Excluded dates break the independence transition chain
  Given account "var-acct" has consecutive days where day 5 is excluded by the quality filter
  When the backtest is requested for "var-acct"
  Then day 4 and day 6 are not treated as consecutive for the independence test

Scenario: A rolling exception count series can be requested
  Given account "var-acct" has 500 days of estimates and outcomes
  When the backtest is requested for "var-acct" with the rolling series enabled
  Then the response includes a 250-day rolling exception count for each requested date
      from the 250th day onward
```

---

### User Story 3 - Discover the Available Method, Look-backs and Measures (Priority: P2)

A developer building the controls for a risk screen (confidence-level checkboxes, a
look-back selector) wants to query what the service actually supports, rather than
hard-coding it, so the controls stay correct if the configuration changes.

**Why this priority**: Convenience and future-proofing for client UIs; neither the
series nor the backtest endpoint depends on it.

**Independent Test**: Request the methods endpoint and verify it lists the configured
look-backs, confidence levels and measures, with no account required.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: The methods endpoint lists the configured look-backs and confidence levels
  Given the service is configured with look-backs "1y", "2y" and "5y" and confidence
      levels 95%, 97.5% and 99%
  When the VaR methods are requested
  Then the response lists all three look-back codes with their business-day lengths
  And it lists all three confidence levels
  And it names the headline (default) look-back

Scenario: The methods endpoint requires no account and always succeeds
  When the VaR methods are requested
  Then the response is 200 regardless of which accounts have been ingested
```

---

### User Story 4 - Clear Handling of Invalid Requests (Priority: P2)

A developer who supplies an unknown account, an unsupported look-back or confidence
level, or an invalid date range gets a clear, predictable outcome rather than a
confusing or crashing response.

**Why this priority**: Predictable errors are needed for a dependable API but add no
new analytical capability.

**Independent Test**: Issue requests with an unknown account, an unsupported look-back,
an unsupported confidence level, and an invalid date range, and verify each produces the
documented outcome.

**Acceptance Scenarios** *(Gherkin format — MUST be independently executable as BDD tests)*:

```gherkin
Scenario: An unsupported look-back is rejected
  When the VaR series is requested for "var-acct" with look-back "3y"
  Then the request is rejected with a client error naming the supported look-backs

Scenario: An unsupported confidence level is rejected
  When the VaR series is requested for "var-acct" with confidence "90%"
  Then the request is rejected with a client error naming the supported confidence levels

Scenario: An unknown account is reported as not found
  Given no account named "missing" exists
  When the VaR series is requested for "missing"
  Then the response is a not-found error, consistent with the performance and VaR run endpoints

Scenario: Start date after end date is rejected
  Given a request with start 2026-06-01 and end 2026-01-01
  When the VaR series is requested for "var-acct"
  Then the request is rejected with a client error describing the invalid date range

Scenario: An account without a position ladder is rejected
  Given an account that has only a capital ledger
  When the VaR series is requested for that account
  Then the request is rejected with a client error consistent with the performance endpoints
```

---

### Edge Cases

- **No stored estimates at all** (never computed, or the range excludes everything
  computed): the series endpoint returns an empty list with status/runs links (not an
  error); the backtest endpoint returns zero observations with every rate/statistic
  null except the counts, which are 0.
- **A date with `quality: "insufficient"`**: it has no stored VaR/ES value. It still
  appears in the series (with null VaR/ES/exception for every confidence level, and its
  quality flag shown), but is always excluded from the backtest's observation count —
  there is no forecast to test. This is automatic and is not affected by the minimum
  quality filter.
- **A date whose outcome is still pending** (the newest computed date): the series
  entry's outcome fields (hypothetical PnL, ladder PnL, both exception flags) are null;
  it is excluded from the backtest.
- **Fewer than two observations for a statistic that needs variance** (e.g. VaR
  stability): that statistic is null rather than zero or an error, consistent with the
  return-histogram endpoint's precedent for undefined statistics.
- **Every observation in the backtest is identical (0 exceptions or all exceptions)**:
  the likelihood-ratio statistics and p-values are still computed (not null) — zero
  exceptions is itself informative and must not be treated as an error.
- **Day-to-day holdings changes**: a date whose stored holdings differ from the
  previous included date's is excluded from the VaR-stability calculation (its
  day-on-day change is not a market-driven move), but still counts as an observation
  for the exception-rate statistics.
- **The rolling exception series requested over fewer than 250 observations**: the
  rolling series is returned empty (never partially computed over a short window).
- **Look-back or confidence value not currently configured**: rejected the same way for
  both the series and backtest endpoints.
- **Start/end omitted, or falling on a non-business day**: resolved exactly as the
  performance endpoints resolve them.

## Requirements *(mandatory)*

### Functional Requirements

**Series endpoint**

- **FR-001**: The service MUST expose `GET /v1/accounts/{account_name}/risk/var`
  returning, for a resolved date range, a configured look-back and one or more
  configured confidence levels, the previously computed VaR/ES series for that account —
  without triggering any new calculation.
- **FR-002**: Account addressing and start/end date resolution, defaulting and
  validation MUST follow the same conventions as the performance endpoints.
- **FR-003**: The `lookback` parameter MUST accept one of the currently configured
  look-back codes (e.g. `1y`, `2y`, `5y`); when omitted, the configured headline
  look-back MUST be used.
- **FR-004**: The `confidence` parameter MUST accept one or more of the currently
  configured confidence levels, repeatable; when omitted, every configured confidence
  level MUST be included.
- **FR-005**: Each date present in the series (every ladder business date in the
  resolved range that has a stored estimate at the requested look-back, regardless of
  quality) MUST report: the as-of date, the outcome date, total market value, scenario
  count, the coverage percentages (actual/proxied/rescaled), and the quality flag.
- **FR-006**: For each requested confidence level, each date's entry MUST report VaR and
  Expected Shortfall both in GBP and as a percentage of that date's total market value,
  using the stored values exactly as computed by the calculation run; dates with quality
  `insufficient` MUST report null instead.
- **FR-007**: Each date's entry MUST report the stored realised hypothetical PnL and
  ladder PnL for its outcome date, and, for each confidence level, whether each of the
  two PnL bases was an exception (a loss larger than that level's VaR); a date whose
  outcome is still pending MUST report these as null rather than computing them.
- **FR-008**: If no estimates exist for the account at all, or none fall within the
  resolved range and look-back, the response MUST be a successful, empty series rather
  than an error, and MUST link to the account's VaR status and VaR runs resources.
- **FR-009**: A `lookback` or `confidence` value outside the currently configured set
  MUST be rejected with a client error naming the supported values.

**Backtest endpoint**

- **FR-010**: The service MUST expose `GET /v1/accounts/{account_name}/risk/var/backtest`
  returning, for the same resolved date range and look-back conventions as the series
  endpoint, backtest statistics for one or more requested confidence levels; omitting
  `confidence` MUST include every configured level, consistent with FR-004.
- **FR-011**: The backtest's observation set for a confidence level MUST be every date
  in the resolved range whose stored estimate at the requested look-back is not of
  quality `insufficient`, whose outcome is not pending, and (if a minimum quality was
  requested) whose quality meets or exceeds it; `insufficient` dates and pending-outcome
  dates MUST always be excluded regardless of the minimum quality parameter.
- **FR-012**: An exception for a given date and confidence level MUST be defined as the
  selected PnL basis's realised loss exceeding that date's stored VaR at that
  confidence level.
- **FR-013**: For each requested confidence level, the response MUST report: the
  observation count, the exception count, the expected number of exceptions (observation
  count × (1 − confidence)), the exception rate, the Kupiec proportion-of-failures
  likelihood ratio and its p-value, the Christoffersen independence likelihood ratio and
  its p-value, the conditional-coverage likelihood ratio and its p-value, a traffic-light
  zone, the list of exception dates, the mean VaR over the observation set, and a VaR
  stability measure.
- **FR-014**: The independence and conditional-coverage statistics MUST treat two
  observation dates as consecutive only when no excluded date falls between them; an
  excluded date MUST break the transition chain rather than being skipped over.
- **FR-015**: The traffic-light zone MUST be determined from the cumulative binomial
  probability of the observed exception count given the observation count and the
  confidence level's nominal exceedance rate: green while that probability is below
  95%, yellow while below 99.99%, red otherwise.
- **FR-016**: The VaR stability measure MUST be the standard deviation of the day-to-day
  log change in VaR at that confidence level, computed only over consecutive included
  dates whose underlying holdings did not change between them.
- **FR-017**: `pnl_basis` MUST accept `hypothetical` (the default) or `ladder`, selecting
  which realised PnL series defines exceptions and all statistics derived from them.
- **FR-018**: A `min_quality` parameter MUST further restrict the observation set to
  dates meeting or exceeding the given quality level (`ok`, more restrictive than the
  default; or `degraded`, the default effective behaviour once `insufficient` is
  excluded).
- **FR-019**: A rolling-exception-series option MUST, when requested, add a 250-day
  rolling exception count for each confidence level, one value per date from the 250th
  included date onward; the option MUST be omittable, defaulting to not included.
- **FR-020**: Statistics that are mathematically undefined for the available
  observations (e.g. any likelihood ratio or stability measure with zero or one
  observation) MUST be returned as null rather than an error; counts MUST always be
  numeric (0 when there are no observations).
- **FR-021**: A `lookback` or `confidence` value outside the currently configured set,
  or an unsupported `pnl_basis` or `min_quality` value, MUST be rejected with a client
  error naming the supported values.

**Methods endpoint**

- **FR-022**: The service MUST expose `GET /v1/risk/var/methods`, requiring no account,
  describing the supported calculation method, every configured look-back (code and
  business-day length), the headline look-back, every configured confidence level, and
  the measures available on the series and backtest endpoints.

**Cross-cutting**

- **FR-023**: These endpoints MUST NOT create, modify, or trigger a VaR calculation run;
  they only read the store feature 012 already maintains.
- **FR-024**: The following MUST be rejected with the same problem-details error
  responses as the performance and VaR run endpoints: an invalid account name; an
  unknown account; an account with no ingested position ladder; a start date later than
  the resolved end date.
- **FR-025**: Every response MUST include `_links` (at minimum `self`; the series and
  backtest responses MUST also link to the account's VaR status and runs resources).
  Every error response MUST follow the existing RFC 7807 conventions, including a
  correlation ID consistent with feature 012's error responses.

### Key Entities

- **VaR Series Entry**: One business date's previously computed estimate and realised
  outcome, scoped to one look-back: scenario count, coverage, quality, per-confidence
  VaR/ES (GBP and %), and the realised hypothetical/ladder PnL and exception flags for
  its outcome date.
- **Backtest Result**: Per confidence level, over a date range and look-back: the
  observation and exception counts, the expected exception count, the exception rate,
  the three likelihood-ratio tests and their p-values, the traffic-light zone, the
  exception dates, the mean VaR, the VaR stability measure, and (optionally) a rolling
  exception count series.
- **Method Description**: The supported calculation method's configured look-backs
  (with the headline marked), confidence levels, and the set of measures the series and
  backtest endpoints expose.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any date and look-back with a stored estimate, every value in the
  series response matches the stored value exactly (counts, quality) or within 1e-9
  relative tolerance (monetary and percentage figures).
- **SC-002**: For a reference backtest data set with a known exception count, every
  reported statistic (exception rate, both likelihood ratios, both p-values, traffic-
  light zone) matches an independently calculated value exactly for integers and within
  1e-9 relative tolerance for decimals.
- **SC-003**: The traffic-light zone matches the Basel 0–4/5–9/10+ exception-count
  thresholds exactly for 250 observations at 99% confidence.
- **SC-004**: A caller can retrieve the series or the backtest for a range of up to 10
  years of daily data in a single request in under 2 seconds under normal load.
- **SC-005**: An account with no completed VaR run returns a successful, empty series
  (not an error) 100% of the time, and the backtest returns zero observations rather
  than failing.
- **SC-006**: Every invalid request class (unsupported look-back, unsupported
  confidence, unknown account, missing ladder, invalid date range) yields a documented,
  predictable outcome with no unhandled failures.

## Assumptions

- Both endpoints are strictly read-only over feature 012's existing per-account store
  (`estimates.csv`, `outcomes.csv`); no new calculation, persistence, or market-data
  call is introduced by this feature.
- The "configured headline look-back" is a new, additive configuration value (default
  `2y`, matching `docs/proposals/value-at-risk.md`'s recommendation); existing
  deployments without it explicitly set continue to work via this default.
- Coverage percentages reported per date are the actual/proxied/rescaled split already
  computed and stored by feature 012, read as-is.
- "Hypothetical PnL" is the primary backtest basis (the Basel-style approach, isolating
  the model from trading activity); "ladder PnL" is offered as an alternative, selected
  via `pnl_basis`.
- The minimum-quality filter and the automatic exclusion of `insufficient`-quality and
  pending-outcome dates apply to the *backtest* endpoint's observation set only; the
  *series* endpoint always returns every date that has a stored estimate, regardless of
  quality, so a caller can see the full picture (including its gaps) in one response.
- "Holdings did not change" between two consecutive included dates, for the VaR
  stability measure, is determined from the same per-date fingerprint feature 012
  already stores for each estimate.
- Kupiec, Christoffersen and the traffic-light zone are computed using only the Python
  standard library (no new third-party dependency), consistent with feature 012 and the
  proposal's own constraint.
- A date's quality ordering, from best to worst, is `ok` > `degraded` > `insufficient`;
  `insufficient` carries no VaR value and is therefore never includable in a backtest
  regardless of the minimum-quality filter.
- Authentication, authorisation, and the existing HATEOAS/RFC 7807 conventions
  (including correlation IDs on error responses) follow feature 012 and the performance
  endpoints unchanged.
- Multi-account/combined and incremental VaR, and any backtest visualisation, remain out
  of scope and are addressed by separate, later features (per the proposal's §11
  delivery plan).
