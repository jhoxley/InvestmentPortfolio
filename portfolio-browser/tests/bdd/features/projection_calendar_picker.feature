Feature: Exact-date projection via the calendar picker on the Projection page
  As a user of the Investment Portfolio Browser
  I want to project to a specific date I choose, not just a preset horizon
  So that I can plan around a retirement date, purchase, or other goal (User Story 2)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded market-value history
    And the Projection page has finished loading its default chart

  Scenario: Picking an exact date projects to that date
    Given the user turns on the "1Y" return toggle
    When the user picks a projection date five and a half years from the start date using the calendar control
    Then the projected line ends exactly on that chosen date

  Scenario: Clicking a preset horizon after picking an exact date replaces the chosen date
    Given the user has picked an exact projection date using the calendar control
    When the user clicks the "1Y" horizon button
    Then the projection now ends one year from the start date, not on the previously chosen date
    And the calendar control shows the date the "1Y" button resolved to

  Scenario: A chosen date that is not later than the start date is rejected
    When the user attempts to pick a projection date on or before the start date
    Then that date is not accepted as the projection target
    And an inline message next to the calendar control explains why it was rejected
    And the chart continues showing the most recently valid projection
