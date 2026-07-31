Feature: Default account performance chart on Performance
  As a user of the Investment Portfolio Browser
  I want the Performance page to show a real chart immediately
  So that I see an account's return measures at a glance with no setup (User Story 1)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded performance history

  Scenario: Chart auto-renders on first load with no selection required
    When the browser loads the Performance page and its chart finishes loading
    Then the Account selector shows the alphabetically-first account selected
    And the date range covers that account's full recorded history
    And a line chart is displayed automatically showing the first returned performance measure

  Scenario: An account with no recorded performance data shows a clear message
    Given portfolio-analysis-service has an account with no recorded performance data
    When the browser loads the Performance page and its chart finishes loading
    Then a "no data" message is shown instead of a broken chart

  Scenario: A failure looking up accounts or measures shows an error state
    Given portfolio-analysis-service is unavailable for account/measure lookups
    When the browser loads the Performance page and its chart finishes loading
    Then an error-state message is shown instead of a chart or an indefinite loading spinner

  Scenario: A failure fetching performance data shows an error state
    Given portfolio-analysis-service is unavailable for performance data
    When the browser loads the Performance page and its chart finishes loading
    Then an error-state message is shown instead of a chart or an indefinite loading spinner
