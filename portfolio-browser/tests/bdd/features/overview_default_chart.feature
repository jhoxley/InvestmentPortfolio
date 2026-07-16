Feature: Default account performance chart on Overview
  As a user of the Investment Portfolio Browser
  I want the Overview page to show a real chart immediately
  So that I see account performance at a glance with no setup (User Story 1)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded history

  Scenario: Chart auto-renders on first load with no selection required
    When the browser loads the Overview page
    Then a line chart is displayed automatically showing the "market_value" metric for the alphabetically-first account

  Scenario: Legend identifies the plotted line
    Given the Overview page has finished loading its default chart
    Then a legend below the chart lists "market_value" with a distinct color

  Scenario: Hovering a point shows date, metric, and value
    Given the Overview page has finished loading its default chart
    When the user hovers over a point on the "market_value" line
    Then a tooltip shows that point's date, metric name, and value

  Scenario: Vertical axis shows GBP amounts
    Given the Overview page has finished loading its default chart
    Then the vertical axis is labeled with GBP amounts
