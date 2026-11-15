Feature: VaR contributions (marginal risk) endpoint

  As a portfolio owner, I want to see which positions or themes drive an account's
  VaR, so I know where risk is concentrated rather than just the single
  portfolio-level number.

  @us1
  Scenario: Contributions grouped by position for a fully computed date
    Given account "contrib-acct" holds "Equity A" worth 60000 and "Equity B" worth 30000 and Cash worth 10000 on 2026-03-09
    And the contributions VaR look-backs are configured as win:3
    And "Equity A" has distinct daily GBP prices covering the 3-day window ending 2026-03-09 starting at 100
    And "Equity B" has distinct daily GBP prices covering the 3-day window ending 2026-03-09 starting at 50
    And a full VaR run is requested for "contrib-acct" and completes
    When the contributions for "contrib-acct" on 2026-03-09 at look-back "win" grouped by "position" are requested
    Then the response status is 200
    And the contributions response has one group for each of "Equity A", "Equity B", "Cash"
    And the sum of component ES across the contributions groups equals the stored total ES
    And requesting the contributions made no new market-data calls

  @us1
  Scenario: Contributions grouped by theme
    Given account "contrib-theme-acct" holds "Equity A" worth 60000 and "Equity B" worth 30000 and Cash worth 10000 on 2026-03-09
    And "Equity A" and "Equity B" share theme "Global"
    And the contributions VaR look-backs are configured as win:3
    And "Equity A" has distinct daily GBP prices covering the 3-day window ending 2026-03-09 starting at 100
    And "Equity B" has distinct daily GBP prices covering the 3-day window ending 2026-03-09 starting at 50
    And a full VaR run is requested for "contrib-theme-acct" and completes
    When the contributions for "contrib-theme-acct" on 2026-03-09 at look-back "win" grouped by "theme" are requested
    Then the response status is 200
    And the contributions response has one group for each of "Global", "Cash"

  @us2
  Scenario: No VaR run has ever covered the requested account and lookback
    Given account "contrib-unrun-acct" holds "Equity A" worth 1000 on 2026-03-09
    When the contributions for "contrib-unrun-acct" on 2026-03-09 at look-back "2y" grouped by "position" are requested
    Then the response status is 200
    And the contributions response is not computed

  @us2
  Scenario: The requested date's VaR quality is insufficient
    Given account "contrib-insufficient-acct" holds "Equity A" worth 1000 on 2026-03-09
    And the contributions VaR look-backs are configured as big:50
    And "Equity A" has distinct daily GBP prices covering the 3-day window ending 2026-03-09 starting at 100
    And a full VaR run is requested for "contrib-insufficient-acct" and completes
    When the contributions for "contrib-insufficient-acct" on 2026-03-09 at look-back "big" grouped by "position" are requested
    Then the response status is 200
    And the contributions response has quality "insufficient"
    And the contributions response groups are empty
    And the contributions response has a total value

  @us3
  Scenario: Invalid group_by value
    Given account "contrib-acct" holds "Equity A" worth 60000 and "Equity B" worth 30000 and Cash worth 10000 on 2026-03-09
    And the contributions VaR look-backs are configured as win:3
    When the contributions for "contrib-acct" on 2026-03-09 at look-back "win" grouped by "sector" are requested
    Then the response status is 422
    And the problem type is "invalid-var-query" naming "group_by"

  @us3
  Scenario: Invalid lookback value reuses the existing problem type
    Given account "contrib-acct" holds "Equity A" worth 60000 and "Equity B" worth 30000 and Cash worth 10000 on 2026-03-09
    When the contributions for "contrib-acct" on 2026-03-09 at look-back "3y" grouped by "position" are requested
    Then the response status is 422
    And the problem type is "invalid-var-query" naming "lookback"
