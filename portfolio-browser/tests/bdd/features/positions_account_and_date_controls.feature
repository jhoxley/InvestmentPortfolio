Feature: Positions page account and date-range exploration
  As a user of the Investment Portfolio Browser
  I want to switch accounts and adjust the date range on the Positions page
  So that I can explore a different account's positions or a different reporting period (FR-003, FR-014)

  Background:
    Given portfolio-analysis-service has multiple accounts with position data

  Scenario: Switching accounts resets the position filter and the date range to "YtD"
    Given the Positions page has finished loading its default view
    When the user selects a different account
    Then the position filter shows every position for the newly selected account
    And the date range shows "YtD" for the newly selected account

  Scenario Outline: Clicking a shortcut updates the date range and refreshes the chart
    Given the Positions page has finished loading its default view
    When the user clicks the "<shortcut>" shortcut button
    Then the "From" date updates to the correct computed date for that shortcut
    And the "To" date is set to the most recently completed business day

    Examples:
      | shortcut |
      | YtD      |
      | 1Y       |
      | 3Y       |
      | 5Y       |
      | All      |

  Scenario: Controls are disabled while a refresh is in flight
    Given the Positions page has finished loading its default view, with a slow backing service
    When the user clicks the "1Y" shortcut button
    Then the Account, From, To, and shortcut controls are disabled until the refresh completes
