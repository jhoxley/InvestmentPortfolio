Feature: Switch which account is being viewed
  As a user with more than one account
  I want to switch which account's performance I'm viewing
  So that I can compare accounts without leaving the Overview page (User Story 2)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded history
    And the Overview page has finished loading its default chart

  Scenario: Every account is listed in the Account control
    Then every account is listed in the Account selector by its account name

  Scenario: Selecting a different account updates the chart
    When the user selects a different account
    Then the chart updates to show that account's performance data

  Scenario: Date range resets to the newly-selected account's own history
    When the user selects a different account
    Then the "from" date defaults to that account's earliest recorded date
    And the "to" date defaults to the most recent completed business day

  Scenario: Switching account patches the page in place without a full reload
    When the user selects a different account
    Then the chart updates without a full browser navigation event
