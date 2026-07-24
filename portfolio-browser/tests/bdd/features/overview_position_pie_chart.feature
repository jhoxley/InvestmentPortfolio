Feature: Overview position weight pie chart
  As a user of the Investment Portfolio Browser
  I want to see my account's position weights as a pie chart on the Overview page
  So that I can see portfolio composition at a glance without navigating away (FR-002-FR-004, FR-002a)

  Background:
    Given portfolio-analysis-service has an account with position data

  Scenario: The pie chart renders with one slice per position
    Given the Overview page has finished loading its default chart
    Then the pie chart shows one slice per position, sized by market-value share
    And any slice of at least 5% share is labeled directly with its position name
    And every slice reveals its exact name, value, and percentage on hover

  Scenario: Changing the account refreshes the pie chart
    Given the Overview page has finished loading its default chart
    When the user selects a different account
    Then the pie chart refreshes to that account's own position weights

  Scenario: Changing the "To" date refreshes the pie chart
    Given the Overview page has finished loading its default chart
    When the user changes the "To" date
    Then the pie chart refreshes to the newly selected date's position weights

  Scenario: An account with no position data shows a "no data" message
    Given portfolio-analysis-service has an account with no position data
    Given the Overview page has finished loading its default chart
    Then a "no data" message is shown in place of the pie chart

  Scenario: The pie chart and winners/losers table stack at tablet width
    Given the Overview page has finished loading its default chart
    When the user views the page at a tablet viewport width
    Then the pie chart and winners/losers table stack vertically instead of side-by-side
