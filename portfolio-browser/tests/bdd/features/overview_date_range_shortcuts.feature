Feature: Date range shortcut buttons on Overview
  As a user viewing the Overview performance chart
  I want one-click shortcuts for common reporting periods
  So that I don't have to manually operate the date pickers (spec 017)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded history
    And the Overview page has finished loading its default chart

  Scenario: Clicking "YtD" sets the date range to year-to-date
    When the user clicks the "YtD" shortcut button
    Then the "from" date is set to 1 January of the current year
    And the "to" date is set to the most recently completed business day
    And the chart refreshes to show only data within that range

  Scenario Outline: Clicking a fixed-offset shortcut sets the "from" date to the correct calendar offset
    When the user clicks the "<label>" shortcut button
    Then the "from" date is set to exactly <years> years before today
    And the chart refreshes to show only data within that range

    Examples:
      | label | years |
      | 1Y    | 1     |
      | 3Y    | 3     |
      | 5Y    | 5     |

  Scenario: Date fields show the exact dates now charted, not the button's label
    When the user clicks the "3Y" shortcut button
    Then the "from" and "to" fields show the exact dates now being charted

  Scenario: A shortcut spanning more history than the account has clamps to the account's earliest date
    Given portfolio-analysis-service has an account with less than 5 years of recorded history
    When the browser loads the Overview page
    And the user clicks the "5Y" shortcut button
    Then the "from" date is set to that account's earliest recorded date
    And the chart shows the account's complete available history with no error

  Scenario: Clicking "All" shows the selected account's complete recorded history
    When the user clicks the "All" shortcut button
    Then the "from" date is set to that account's earliest recorded date
    And the chart refreshes to show only data within that range

  Scenario: Clicking "All" after switching accounts reflects the newly-selected account
    When the user selects a different account
    And the user clicks the "All" shortcut button
    Then the "from" date is set to that account's earliest recorded date

  Scenario: Shortcut buttons are disabled while a chart refresh is in flight
    Given portfolio-analysis-service takes a moment to respond
    When the user clicks the "1Y" shortcut button without waiting for the refresh to finish
    Then all shortcut buttons are disabled while the chart refreshes
    And all shortcut buttons are enabled once the chart has refreshed
