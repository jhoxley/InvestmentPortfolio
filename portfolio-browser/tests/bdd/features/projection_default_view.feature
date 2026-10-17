Feature: Preset horizon projection on the Projection page
  As a user of the Investment Portfolio Browser
  I want to project my portfolio's value forward using a preset horizon
  So that I get a quick sense of where my portfolio could be years from now (User Story 1)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded market-value history

  Scenario: The Income page no longer exists and Projection takes its place
    When the browser loads the app
    Then there is no "Income" navigation entry
    And there is a "Projection" navigation entry in the position "Income" used to occupy

  Scenario: A preset horizon button projects forward from the start date
    Given the Projection page has finished loading its default chart
    When the user turns on the "5Y" return toggle
    And the user clicks the "10Y" horizon button
    Then the chart shows the account's historical market value up to the start date
    And a single projected line labelled "5Y" continues from the start date's value to ten years from the start date
    And the historical and projected lines are visually distinguishable

  Scenario Outline: Each preset horizon button projects to the matching number of years ahead
    Given the Projection page has finished loading its default chart
    When the user turns on the "3Y" return toggle
    And the user clicks the "<horizon>" horizon button
    Then the projected line's end date is <years> years after the start date

    Examples:
      | horizon | years |
      | 1Y      | 1     |
      | 5Y      | 5     |
      | 10Y     | 10    |
      | 20Y     | 20    |

  Scenario: A return with insufficient history produces no projection, not an error
    Given portfolio-analysis-service has an account with under three years of history
    And the Projection page has finished loading its default chart
    When the user turns on the "3Y" return toggle
    And the user clicks the "10Y" horizon button
    Then no projected line is shown for "3Y"
    And the historical market-value line still renders normally with no error shown

  Scenario: With no return selected, the historical line still renders on its own
    Given the Projection page has finished loading its default chart
    Then the chart shows only the historical market-value line
    And no error or empty-state message is shown
