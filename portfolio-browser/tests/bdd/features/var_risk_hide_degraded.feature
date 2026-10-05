Feature: Hide degraded-quality dates on the Value at Risk tab
  As a user of the Investment Portfolio Browser
  I want to set aside degraded-quality dates
  So that a run of lower-quality data doesn't distort my reading of the chart (User Story 6)

  Background:
    Given portfolio-analysis-service has a VaR series with a degraded-quality day

  Scenario: Hiding degraded-quality dates removes them from the chart
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    And I turn on "hide degraded-quality dates"
    Then the degraded-quality date's bar and overlay point no longer appear on the chart

  Scenario: Turning the toggle off restores degraded-quality dates
    Given the browser has loaded the Risk page and its content finished loading
    When I select the "Value at Risk" tab
    And I turn on "hide degraded-quality dates"
    And I turn off "hide degraded-quality dates"
    Then the degraded-quality date's bar reappears on the chart
