Feature: Positions page default view
  As a user of the Investment Portfolio Browser
  I want the Positions page to show a sensible default view immediately
  So that the menu entry is useful without any manual configuration (FR-001, FR-012, SC-001)

  Background:
    Given portfolio-analysis-service has multiple accounts with position data

  Scenario: First navigation defaults to the first account, YtD, and all positions
    When the browser loads the Positions page
    Then the Account selector shows the alphabetically-first account selected
    And the date range shows "YtD" for that account
    And the position filter shows every position for that account selected

  Scenario: The default view renders a chart for the default attribute across all positions
    When the browser loads the Positions page
    Then a chart is shown with one line per position

  Scenario: An account with no recorded position data shows a clear message
    Given portfolio-analysis-service has an account with no position data
    When the browser loads the Positions page
    Then a "no data" message is shown instead of a broken chart
