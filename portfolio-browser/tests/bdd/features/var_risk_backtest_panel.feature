Feature: Value at Risk backtest summary panel
  As a user of the Investment Portfolio Browser
  I want a quantified reliability assessment alongside the VaR chart
  So that I can judge whether the risk model can be trusted for this account (User Story 2)

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: The backtest panel reports the headline reliability figures
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then the backtest panel shows exceedances observed and expected, both p-values, a pass/fail rating, mean VaR and stability

  Scenario: The panel reflects the same confidence level as the chart
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    And I select only the 99% confidence level
    Then the backtest panel shows figures for the 99% confidence level only

  Scenario: The panel shares the histogram table's visual style
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then the backtest panel is rendered as a labelled table/grid matching the histogram's statistics table style

  Scenario: Multiple selected confidence levels appear as columns of one table, not separate tables
    Given the browser has loaded the Risk page and its content finished loading
    When the Value at Risk section finishes loading
    Then the backtest panel is exactly one table
    When I select only the 99% confidence level
    Then the backtest panel is still exactly one table
    And it has exactly one value column
