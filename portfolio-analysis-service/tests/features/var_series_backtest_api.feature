Feature: VaR series, backtest and methods endpoints

  As a developer building a risk chart and a developer assessing model quality, I want
  read-only access to feature 012's precomputed VaR store, and a discoverable description
  of the supported method, so I can show forecasts alongside outcomes and assess fit
  without triggering any new calculation.

  @us1
  Scenario: A computed date's series entry matches the stored estimate and outcome
    Given account "var-acct" has a completed VaR run covering 2026-03-02 at look-back "2y"
    When the VaR series is requested for "var-acct" from 2026-03-02 to 2026-03-02 at look-back "2y"
    Then the single returned entry's scenario count, coverage, quality, VaR and ES at every confidence level match the stored estimate exactly
    And its hypothetical and ladder PnL match the stored outcome exactly

  @us1
  Scenario: Only the requested look-back's estimates are returned
    Given account "var-acct" has completed estimates at look-backs "1y", "2y" and "5y" for 2026-03-02
    When the VaR series is requested for "var-acct" at look-back "1y"
    Then the returned entry's figures are the "1y" estimate, not "2y" or "5y"

  @us1
  Scenario: Only the requested confidence levels are returned
    Given account "var-acct" has a completed estimate for 2026-03-02 at 95%, 97.5% and 99%
    When the VaR series is requested for "var-acct" with confidence 95% only
    Then the returned entry includes only the 95% VaR/ES figures

  @us1
  Scenario: Omitting confidence returns every configured level
    Given account "var-acct" has a completed estimate for 2026-03-02 at 95%, 97.5% and 99%
    When the VaR series is requested for "var-acct" with no confidence parameter
    Then the returned entry includes every configured confidence level

  @us1
  Scenario: An account with nothing computed returns an empty series, not an error
    Given account "var-acct" has an ingested position ladder but no completed VaR run
    When the VaR series is requested for "var-acct"
    Then the response is 200 with an empty series
    And the response links to the account's VaR status and runs resources

  @us1
  Scenario: An exception flag reflects a loss beyond that confidence level's VaR
    Given a stored estimate for 2026-03-02 with 95% VaR of 1000 GBP
    And the stored outcome's hypothetical PnL for that date is -1200 GBP
    When the VaR series is requested for "var-acct"
    Then that date's 95% entry reports the hypothetical PnL as an exception

  @us4
  Scenario: An unsupported look-back is rejected
    When the VaR series is requested for "var-acct" with look-back "3y"
    Then the request is rejected with a client error naming the supported look-backs

  @us4
  Scenario: An unsupported confidence level is rejected
    When the VaR series is requested for "var-acct" with confidence "90%"
    Then the request is rejected with a client error naming the supported confidence levels

  @us4
  Scenario: An unknown account is reported as not found
    Given no account named "missing" exists
    When the VaR series is requested for "missing"
    Then the response is a not-found error, consistent with the performance and VaR run endpoints

  @us4
  Scenario: Start date after end date is rejected
    Given a request with start 2026-06-01 and end 2026-01-01
    When the VaR series is requested for "var-acct"
    Then the request is rejected with a client error describing the invalid date range

  @us4
  Scenario: An account without a position ladder is rejected
    Given an account that has only a capital ledger
    When the VaR series is requested for that account
    Then the request is rejected with a client error consistent with the performance endpoints

  @us2
  Scenario: Exception count matches the number of losses beyond VaR
    Given account "bt-acct" has 250 days of 99% VaR estimates and hypothetical outcomes
    And exactly 6 of those days have a loss larger than that day's 99% VaR
    When the backtest is requested for "bt-acct" at 99% confidence
    Then the reported observation count is 250 and the exception count is 6

  @us2
  Scenario: Statistics are computed against hypothetical PnL by default
    Given account "bt-acct" has both hypothetical and ladder outcomes stored
    And the two PnL bases disagree on whether one day is an exception
    When the backtest is requested for "bt-acct" with no pnl_basis parameter
    Then the exception count reflects the hypothetical PnL basis

  @us2
  Scenario: Requesting the ladder PnL basis changes which days count as exceptions
    Given account "bt-acct" has both hypothetical and ladder outcomes stored
    And the two PnL bases disagree on whether one day is an exception
    When the backtest is requested for "bt-acct" with pnl_basis "ladder"
    Then the exception count reflects the ladder PnL basis instead

  @us2
  Scenario: A minimum quality filter excludes lower-quality dates from the backtest
    Given account "bt-acct" has 10 "ok" days and 5 "degraded" days in the requested range
    When the backtest is requested for "bt-acct" with a minimum quality of "ok"
    Then the reported observation count is 10

  @us2
  Scenario: Insufficient-quality dates are always excluded, even without a filter
    Given account "bt-acct" has 10 "ok" days and 3 "insufficient" days in the requested range
    When the backtest is requested for "bt-acct" with no minimum quality parameter
    Then the reported observation count is 10, not 13

  @us2
  Scenario: A rolling exception count series can be requested
    Given account "bt-acct" has 500 days of estimates and outcomes
    When the backtest is requested for "bt-acct" with the rolling series enabled
    Then the response includes a 250-day rolling exception count for each requested date from the 250th day onward

  @us4
  Scenario: An unsupported pnl_basis is rejected
    Given account "bt-acct" has 10 days of estimates and outcomes
    When the backtest is requested for "bt-acct" with pnl_basis "both"
    Then the request is rejected with a client error naming the supported pnl_basis values

  @us4
  Scenario: An unsupported min_quality is rejected
    Given account "bt-acct" has 10 days of estimates and outcomes
    When the backtest is requested for "bt-acct" with a minimum quality of "insufficient"
    Then the request is rejected with a client error naming the supported min_quality values

  @us3
  Scenario: The methods endpoint lists the configured look-backs and confidence levels
    When the VaR methods are requested
    Then the response lists all three look-back codes with their business-day lengths
    And it lists all three confidence levels
    And it names the headline look-back

  @us3
  Scenario: The methods endpoint requires no account and always succeeds
    When the VaR methods are requested
    Then the response is 200 regardless of which accounts have been ingested
