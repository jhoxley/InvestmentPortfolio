Feature: Explore a different account or time period on Performance
  As a user of the Investment Portfolio Browser
  I want to switch accounts and adjust the date range on the Performance page
  So that I can look at a different account's performance or a different
  reporting period (User Story 2)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded performance history

  Scenario: Switching accounts resets the date range to the new account's full history
    Given the Performance page has finished loading its default chart
    When the user selects a different account
    Then the chart updates to show that account's performance data
    And the "from" date defaults to that account's earliest recorded date

  Scenario: Clicking "ITD" and clicking "All" resolve to the identical "From" date
    Given the Performance page has finished loading its default chart
    When the user clicks the "ITD" shortcut button
    Then the "from" date is set to that account's earliest recorded date
    When the user clicks the "All" shortcut button
    Then the "from" date is set to that account's earliest recorded date

  Scenario: Clicking a year-based shortcut updates the date range and chart
    Given the Performance page has finished loading its default chart
    When the user clicks the "3Y" shortcut button
    Then the "from" date is set to exactly 3 years before today
    And the "to" date is set to the most recently completed business day
    And the chart refreshes to show only data within that range

  Scenario: Controls are disabled while a refresh is in flight
    Given portfolio-analysis-service takes a moment to respond with performance data
    And the Performance page has finished loading its default chart
    When the user clicks the "1Y" shortcut button without waiting for the refresh to finish
    Then all shortcut buttons are disabled while the chart refreshes
    And all shortcut buttons are enabled once the chart has refreshed
