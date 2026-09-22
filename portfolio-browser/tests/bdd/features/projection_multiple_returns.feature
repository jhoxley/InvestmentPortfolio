Feature: Comparing multiple return scenarios side by side on the Projection page
  As a user of the Investment Portfolio Browser
  I want to see more than one projected return at once
  So that I can judge a range of plausible outcomes rather than commit to one guess (User Story 3)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded market-value history
    And the Projection page has finished loading its default chart

  Scenario: Selecting two returns draws two projected lines from the same starting point
    When the user turns on the "3Y" return toggle
    And the user turns on the "5Y" return toggle
    And the user clicks the "10Y" horizon button
    Then two projected lines are shown, labelled "3Y" and "5Y"
    And both lines begin at the same point, the start date's market value
    And both lines end on the same date, ten years from the start date

  Scenario: Selecting a third return adds a third distinct line without disturbing the other two
    Given the user turns on the "3Y" return toggle
    And the user turns on the "5Y" return toggle
    And the user clicks the "10Y" horizon button
    When the user turns on the "Ann. ITD" return toggle
    Then a third projected line labelled "Ann. ITD" appears
    And the lines labelled "3Y" and "5Y" are unchanged
