Feature: Choose which metrics to compare
  As a user comparing performance measures
  I want to turn individual metrics on or off
  So that I only see the lines I care about (User Story 4)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded history
    And the Overview page has finished loading its default chart

  Scenario: Hovering a toggle shows its description
    When the user hovers over the "capital" metric toggle
    Then a tooltip describing the "capital" metric is shown

  Scenario: Turning on a second metric adds a distinctly-colored line
    When the user turns on the "capital" metric toggle
    Then the chart shows a line for "capital" in a distinct color from "market_value"
    And the legend lists both "market_value" and "capital"

  Scenario: Turning off a metric removes its line and legend entry
    Given the user has turned on the "capital" metric toggle
    When the user turns off the "market_value" metric toggle
    Then the chart no longer shows a line for "market_value"
    And the chart still shows a line for "capital"

  Scenario: Navigating away hides the metric-toggle panel
    When the user clicks the "Positions" navigation item
    Then no metric-toggle panel is shown
