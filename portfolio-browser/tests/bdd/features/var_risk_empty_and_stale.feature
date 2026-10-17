Feature: Empty and stale Value at Risk data states
  As a user of the Investment Portfolio Browser
  I want a clear explanation when VaR has never been computed or is behind the ladder
  So that I don't mistake missing data for a broken page (User Story 5)

  Scenario: An account with no calculated risk data shows an explanatory empty state
    Given portfolio-analysis-service has an account with no calculated VaR data
    When the browser loads the Risk page and its content finishes loading
    And the Value at Risk section finishes loading
    Then no chart or backtest panel is shown
    And an explanatory message describing how to run a calculation is shown

  Scenario: An account whose risk data lags its trading activity shows a banner
    Given portfolio-analysis-service has an account whose VaR data is behind its trading activity
    When the browser loads the Risk page and its content finishes loading
    And the Value at Risk section finishes loading
    Then a banner states how many dates are missing
    And the chart and panel still render
