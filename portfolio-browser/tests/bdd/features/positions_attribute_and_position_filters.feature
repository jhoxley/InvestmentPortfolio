Feature: Positions page attribute and position filtering
  As a user of the Investment Portfolio Browser
  I want to toggle attributes and narrow the position filter on the Positions page
  So that I can focus the chart and table on exactly what I want to compare (FR-004, FR-005, FR-020, FR-021)

  Background:
    Given portfolio-analysis-service has multiple accounts with position data
    And the Positions page has finished loading its default view

  Scenario: Toggling a second attribute on updates the chart
    When the user toggles the "quantity" attribute on
    Then the chart includes a line for "quantity"

  Scenario: Selecting a subset of positions narrows the chart
    When the user narrows the position filter to a single position
    Then the chart shows only that position

  Scenario: Deselecting every attribute shows a prompt instead of a blank chart
    When the user deselects every attribute
    Then a prompt to select at least one attribute is shown

  Scenario: Deselecting every position shows a prompt instead of a blank chart
    When the user deselects every position
    Then a prompt to select at least one position is shown
