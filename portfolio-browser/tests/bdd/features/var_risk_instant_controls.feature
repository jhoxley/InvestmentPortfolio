Feature: Instant confidence/units/PnL-basis controls on the Value at Risk section
  As a user of the Investment Portfolio Browser
  I want confidence, units and PnL-basis changes to update immediately
  So that I can explore the view without waiting for a new request each time (User Story 3)

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: Changing the selected confidence levels updates instantly
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I select only the 99% confidence level
    Then no new VaR series or backtest request was made

  Scenario: Changing units updates the displayed scale instantly
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I switch units to percentage
    Then no new VaR series or backtest request was made

  Scenario: Changing PnL basis updates which days are exceedances instantly
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I switch PnL basis to ladder
    Then no new VaR series or backtest request was made
