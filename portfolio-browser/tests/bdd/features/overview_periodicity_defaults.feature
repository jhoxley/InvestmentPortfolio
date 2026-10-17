Feature: Duration-derived periodicity defaults on Overview
  As a user who has not chosen a periodicity myself
  I want a sensible interval derived from how long my date range is
  So that long ranges are legible without any extra interaction (spec 021, US3)

  Background:
    Given portfolio-analysis-service has a short-history account and a ten-year-history account
    And the Overview page has finished loading its default chart

  Scenario Outline: The interval is derived from the length of the date range
    When the user sets the date range to <start> through 2026-09-21
    Then the active periodicity button is "<interval>"

    Examples:
      | start      | interval |
      | 2026-03-21 | day      |
      | 2025-09-21 | day      |
      | 2024-09-21 | month    |
      | 2023-09-21 | month    |
      | 2022-09-21 | quarter  |
      | 2021-09-21 | quarter  |
      | 2016-09-21 | year     |

  Scenario: Clicking a long-range shortcut derives a coarser interval automatically
    When the user selects account "TEN-YEAR-PORTFOLIO"
    And the user clicks the "5Y" shortcut button
    Then the active periodicity button is "quarter"

  Scenario: Switching to an account with a much longer history derives a coarser interval
    When the user selects account "TEN-YEAR-PORTFOLIO"
    Then the active periodicity button is "year"

  Scenario Outline: "week" is never chosen automatically
    When the user sets the date range to <start> through 2026-09-21
    Then the active periodicity button is not "week"

    Examples:
      | start      |
      | 2026-09-21 |
      | 2025-09-21 |
      | 2016-09-21 |

  Scenario: An explicit choice is not overridden by a later date-range change
    Given the user selects account "TEN-YEAR-PORTFOLIO"
    And the user selects periodicity "month"
    When the user clicks the "All" shortcut button
    Then the active periodicity button is "month"

  Scenario: An explicit choice survives an account switch
    Given the user selects account "TEN-YEAR-PORTFOLIO"
    And the user selects periodicity "quarter"
    When the user selects account "SHORT-HISTORY-PORTFOLIO"
    Then the active periodicity button is "quarter"
