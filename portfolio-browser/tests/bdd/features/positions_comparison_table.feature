Feature: Positions page comparison table
  As a user of the Investment Portfolio Browser
  I want a compact table below the chart comparing each position's start and current values
  So that I can see at a glance which positions moved up or down over the period (FR-017-FR-019)

  Background:
    Given portfolio-analysis-service has multiple accounts with position data
    And the Positions page has finished loading its default view

  Scenario: The table shows one row per position with a value/(prev) column pair
    Then the comparison table has one row per plotted position
    And each row has a "market_value" column and a "market_value (prev)" column

  Scenario: A risen position is shaded light green
    Then the row for the position whose value rose is shaded light green

  Scenario: A fallen position is shaded light red
    Then the row for the position whose value fell is shaded light red

  Scenario: An unchanged position has no shading
    Then the row for the position whose value held steady has no background shading

  Scenario: The table stays in sync with the chart after a selection change
    When the user toggles the "quantity" attribute on
    Then the comparison table gains a "quantity" column pair matching the chart's selection
