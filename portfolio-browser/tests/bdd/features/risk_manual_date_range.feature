Feature: Manual date range editing on the Risk page
  As a user of the Investment Portfolio Browser
  I want to edit the start/end dates directly on the Risk page
  So that I can inspect an exact, non-standard window (User Story 3)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded return history
    And the Risk page has finished loading its default view

  Scenario: Manually editing either date refreshes the view
    When the user sets a custom date range on the Risk page
    Then the chart and table on the Risk page refresh to reflect exactly that custom range

  Scenario: Switching accounts resets the range to that account's own default
    When the user selects a different account on the Risk page
    Then the date range on the Risk page resets to that account's own default range
    And the chart and table on the Risk page refresh for the newly selected account

  Scenario: An end date not after the start date is rejected
    When the user sets an end date that is not after the start date on the Risk page
    Then an inline validation message is shown on the Risk page
    And the chart and table on the Risk page continue showing the most recently valid data
