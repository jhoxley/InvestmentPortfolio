Feature: Single continuous Risk page
  As a user of the Investment Portfolio Browser
  I want the return histogram and Value at Risk content on one page
  So that I can see both without clicking between tabs (027 User Story 1)

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: The Risk page has no tab control
    When the browser loads the Risk page and its content finishes loading
    Then there is no tab control on the page

  Scenario: The histogram section is visible without any interaction
    When the browser loads the Risk page and its content finishes loading
    Then the return histogram chart and statistics table are visible

  Scenario: Scrolling reveals the Value at Risk section below the histogram
    Given the browser has loaded the Risk page and its content finished loading
    Then the Value at Risk controls, chart and backtest panel are visible below the histogram section

  Scenario: The shared parameters bar is not duplicated by the merge
    Given the browser has loaded the Risk page and its content finished loading
    Then the shared account selector, date range and shortcut buttons appear exactly once
