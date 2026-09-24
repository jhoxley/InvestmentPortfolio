Feature: Duration-derived periodicity defaults on the Projection page
  As a user who has not chosen a periodicity myself
  I want a sensible interval derived from the span being plotted
  So that a long projection is legible without any extra interaction (spec 023, US2)

  Scenario Outline: The interval is derived from the plotted span
    Given portfolio-analysis-service has an account whose history starts on <earliest>
    And the Projection page has finished loading its default chart
    When the user picks the projection date <target> using the calendar control
    Then the active periodicity button is "<interval>"
    And the chart is requested at the "<interval>" interval

    Examples:
      | earliest   | target     | interval |
      | 2026-03-22 | 2026-09-23 | day      |
      | 2025-09-23 | 2026-09-23 | day      |
      | 2024-09-23 | 2026-09-23 | month    |
      | 2023-09-23 | 2026-09-23 | month    |
      | 2022-09-23 | 2026-09-23 | quarter  |
      | 2021-09-23 | 2026-09-23 | quarter  |
      | 2016-09-23 | 2026-09-23 | year     |

  Scenario: Clicking a longer horizon button derives a coarser interval automatically
    Given portfolio-analysis-service has an account whose history starts on 2023-09-23
    And the Projection page has finished loading its default chart
    And the user clicks the "1Y" horizon button
    And the active periodicity button is "quarter"
    When the user clicks the "20Y" horizon button
    Then the active periodicity button is "year"
    And the chart is requested at the "year" interval

  Scenario Outline: "week" is never chosen automatically
    Given portfolio-analysis-service has an account whose history starts on <earliest>
    And the Projection page has finished loading its default chart
    When the user picks the projection date 2026-09-23 using the calendar control
    Then the active periodicity button is not "week"

    Examples:
      | earliest   |
      | 2026-09-22 |
      | 2025-09-22 |
      | 2016-09-22 |

  Scenario: An explicit choice is not overridden by a later horizon click
    Given portfolio-analysis-service has an account whose history starts on 2023-09-23
    And the Projection page has finished loading its default chart
    And the user clicks the "1Y" horizon button
    And the user selects periodicity "month" on Projection
    When the user clicks the "20Y" horizon button
    Then the active periodicity button is "month"
    And the chart is requested at the "month" interval

  Scenario: An explicit choice survives an account switch
    Given portfolio-analysis-service has multiple accounts with recorded market-value history
    And the Projection page has finished loading its default chart
    And the user selects periodicity "quarter" on Projection
    When the user switches to the account "ZZZ-SIPP"
    And the user clicks the "10Y" horizon button
    Then the active periodicity button is "quarter"
    And the chart is requested at the "quarter" interval for account "ZZZ-SIPP"
