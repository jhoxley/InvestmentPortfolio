Feature: Narrow or widen the date range
  As a user analysing a specific period
  I want to adjust the "from" and "to" dates
  So that I can focus the chart on a period of interest (User Story 3)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded history
    And the Overview page has finished loading its default chart

  Scenario: A valid narrower range updates the chart
    When the user sets the "from" date to a later valid date
    Then the chart updates to show only data within the new range

  Scenario: A "to" date after today is prevented
    Then the "to" date picker does not allow a date later than today

  Scenario: A "from" date after the current "to" date is prevented
    Then the "from" date picker does not allow a date later than the current "to" date
