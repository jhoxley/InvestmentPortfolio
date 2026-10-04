Feature: VaR series, backtest and methods endpoints

  As a developer building a risk chart and a developer assessing model quality, I want
  read-only access to feature 012's precomputed VaR store, and a discoverable description
  of the supported method, so I can show forecasts alongside outcomes and assess fit
  without triggering any new calculation.

  @us1
  Scenario: A computed date's series entry matches the stored estimate and outcome
    Given account "var-acct" has a completed VaR run covering 2026-03-02 at look-back "2y"
    When the VaR series is requested for "var-acct" from 2026-03-02 to 2026-03-02 at look-back "2y"
    Then the single returned entry's scenario count, coverage, quality, VaR and ES at every
        confidence level match the stored estimate exactly
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
