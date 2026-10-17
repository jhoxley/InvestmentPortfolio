Feature: Positions page stacked area toggle
  As a user of the Investment Portfolio Browser
  I want to switch between a line chart and a stacked area chart on the Positions page
  So that I can see how a single attribute is composed across positions (FR-006-FR-011)

  Background:
    Given portfolio-analysis-service has multiple accounts with position data
    And the Positions page has finished loading its default view

  Scenario: Turning "Stacked area graph" on with one attribute renders a stacked area chart
    When the user turns "Stacked area graph" on
    Then the chart renders as a stacked area chart

  Scenario: Turning "Stacked area graph" off reverts to a line chart
    Given the user has turned "Stacked area graph" on
    When the user turns "Stacked area graph" off
    Then the chart renders as a line chart

  Scenario: Selecting a second attribute while stacked automatically turns it off
    Given the user has turned "Stacked area graph" on
    When the user toggles the "quantity" attribute on
    Then "Stacked area graph" is turned off automatically
    And the chart renders as a line chart with both attributes

  Scenario: The toggle is disabled while more than one attribute is selected
    When the user toggles the "quantity" attribute on
    Then "Stacked area graph" cannot be switched on
