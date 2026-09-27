Feature: Preset range shortcut buttons on the Risk page
  As a user of the Investment Portfolio Browser
  I want one-click 10Y/1Y/3Y/5Y/All trailing windows on the Risk page
  So that I can quickly compare volatility over different horizons (User Story 2)

  Background:
    Given portfolio-analysis-service has an account with over ten years of recorded return history
    And the Risk page has finished loading its default view

  Scenario Outline: Each preset button resolves to the matching trailing window
    When the user clicks the "<label>" shortcut button on the Risk page
    Then the "from" date on the Risk page is set to <expected>
    And the chart and table on the Risk page refresh

    Examples:
      | label | expected                                  |
      | 1Y    | exactly 1 years before today              |
      | 3Y    | exactly 3 years before today              |
      | 5Y    | exactly 5 years before today              |
      | 10Y   | exactly 10 years before today             |
      | All   | that account's earliest recorded date     |

  Scenario: A preset window with too little history clamps to the earliest date
    Given portfolio-analysis-service has an account with two years of recorded return history
    And the Risk page has finished loading its default view
    When the user clicks the "10Y" shortcut button on the Risk page
    Then the "from" date on the Risk page is set to that account's earliest recorded date
    And the chart and table on the Risk page refresh with no error shown
