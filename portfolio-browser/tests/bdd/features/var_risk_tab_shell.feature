Feature: Value at Risk tab shell on the Risk page
  As a user of the Investment Portfolio Browser
  I want a "Value at Risk" tab alongside the existing return histogram
  So that I can switch between the two views without losing my account/date selection

  Background:
    Given portfolio-analysis-service has an account with a completed VaR calculation

  Scenario: The Value at Risk tab exists alongside the return histogram tab
    When the browser loads the Risk page and its content finishes loading
    Then there is a "Value at Risk" tab next to the "Return Histogram" tab

  Scenario: Switching tabs keeps the shared account and date controls unchanged
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    Then the account selector, date range and shortcut buttons are the same DOM elements as on the "Return Histogram" tab
