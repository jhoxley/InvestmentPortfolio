Feature: Historical-simulation VaR calculation runs

  As a developer, I want a VaR calculation run to compute and store VaR and Expected
  Shortfall for every business date in an account's position ladder, so that risk can
  later be read back quickly without recomputing it per request.

  @us1
  Scenario: A full run computes VaR and ES for every ladder date and look-back
    Given account "var-acct" holds "Equity A" and "Equity B" with daily GBP prices from 2026-01-02 to 2026-03-06
    And the VaR look-backs are configured as 1y:3, 2y:5
    When a full VaR run is requested for "var-acct" and completes
    Then the run status is "succeeded"
    And every business date in the ladder has an estimate for look-back "1y" and "2y"
    And every estimate's 99% VaR is at least its 97.5% VaR, which is at least its 95% VaR
    And every estimate's Expected Shortfall is at least its VaR at the same confidence level

  @us1
  Scenario: VaR matches a hand-computed reference value
    Given account "var-acct" holds "Equity A" worth 60000 and "Equity B" worth 30000 and Cash worth 10000 on 2026-03-02
    And the VaR look-backs are configured as win:5
    And the observed returns of "Equity A" and "Equity B" on the 5 business days ending 2026-03-02 are "-1.2%,0.4%", "0.5%,-2.0%", "-3.1%,-2.5%", "0.8%,1.1%", "-0.2%,0.3%"
    When a full VaR run is requested for "var-acct" and completes
    Then the stored 95% VaR for 2026-03-02 at look-back "win" is 2610 GBP

  @us1
  Scenario: Low-information scenario days are excluded from the scenario count
    Given account "var-acct" holds "Equity A" worth 60000 and "Equity B" worth 40000 on 2026-03-02
    And the VaR look-backs are configured as win:5
    And "Equity A" has no observed price on 2026-02-26 within the 5-day window
    When a full VaR run is requested for "var-acct" and completes
    Then the stored scenario count for 2026-03-02 at look-back "win" is 4

  @us1
  Scenario: A run can be restricted to a date range
    Given account "var-acct" holds "Equity A" with daily GBP prices from 2026-01-02 to 2026-03-06
    And the VaR look-backs are configured as win:5
    When a full VaR run is requested for "var-acct" from 2026-03-02 to 2026-03-04 and completes
    Then only dates from 2026-03-02 to 2026-03-04 have an estimate for look-back "win"

  @us2
  Scenario: Creating a run is acknowledged immediately
    Given account "var-acct" holds "Equity A" with daily GBP prices from 2026-01-02 to 2026-03-06
    When a VaR run is requested for "var-acct"
    Then the response status is 202
    And the response has a run identifier and a status of "queued" or "running"

  @us2
  Scenario: Only one active run per account
    Given account "var-acct" holds "Equity A" with daily GBP prices from 2026-01-02 to 2026-03-06
    And a VaR run for "var-acct" is already queued
    When a VaR run is requested for "var-acct"
    Then the response status is 409
    And the response links to the active run

  @us2
  Scenario: Reading an unknown run is reported as not found
    Given account "var-acct" holds "Equity A" with daily GBP prices from 2026-01-02 to 2026-03-06
    When the VaR run "does-not-exist" is requested for "var-acct"
    Then the response status is 404

  @us2
  Scenario: Interrupted runs are recovered at startup
    Given account "var-acct" has a VaR run record stuck in "running" status
    When the service recovers interrupted runs
    Then that run's status is "failed" with reason "interrupted"
