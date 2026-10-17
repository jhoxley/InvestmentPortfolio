Feature: Periodicity control on Overview
  As a user viewing the Overview performance chart
  I want to choose how densely the chart is plotted
  So that a multi-year chart is readable instead of showing every business day (spec 021)

  Background:
    Given portfolio-analysis-service has an account with ten years of daily-priced history
    And the Overview page has finished loading its default chart
    And the user sets the date range to 2016-01-04 through 2025-12-31

  Scenario: The Periodicity control is present and offers the five documented intervals
    Then a control labelled "Periodicity" is shown in the parameters bar
    And its options are exactly "day", "week", "month", "quarter" and "year", in that order

  Scenario: Selecting a coarser periodicity redraws the chart at that interval
    When the user selects periodicity "year"
    Then the chart shows exactly 10 points
    And the selected account, date range and metrics are unchanged

  Scenario Outline: Each interval option maps to the matching aggregation on the data service
    When the user selects periodicity "<option>"
    Then the chart shows exactly <points> points

    Examples:
      | option  | points |
      | week    | 522    |
      | month   | 120    |
      | quarter | 40     |
      | year    | 10     |

  Scenario: Selecting "day" reproduces the pre-existing per-business-day chart
    When the user selects periodicity "day"
    Then the chart shows exactly 2608 points
