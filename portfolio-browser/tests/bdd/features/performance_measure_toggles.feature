Feature: Choose which return measures to display on Performance
  As a user of the Investment Portfolio Browser
  I want to toggle performance measures on and off
  So that I can focus the chart on exactly the return metrics I want to see
  (User Story 3)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded performance history

  Scenario: Toggling a second measure on adds a distinct line without affecting the first
    Given the Performance page has finished loading its default chart
    When the user turns on the "1Y" measure toggle
    Then the chart shows a line for "1Y" in a distinct color from "ITD"
    And the legend lists both "ITD" and "1Y"

  Scenario: Toggling a measure off removes its line
    Given the Performance page has finished loading its default chart
    When the user turns on the "1Y" measure toggle
    And the user turns off the "1Y" measure toggle
    Then the chart no longer shows a line for "1Y"
    And the chart still shows a line for "ITD"

  Scenario: Deselecting every measure shows a prompt instead of a blank chart
    Given the Performance page has finished loading its default chart
    When the user turns off every measure toggle
    Then a prompt to select at least one measure is shown instead of a chart
