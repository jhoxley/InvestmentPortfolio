Feature: Periodicity control on the Projection page
  As a user projecting my portfolio forward
  I want the same Periodicity control I use on Overview and Positions
  So that I can choose how densely the historical and projected lines are plotted (spec 023, US1)

  Background:
    Given portfolio-analysis-service has multiple accounts with recorded market-value history
    And the Projection page has finished loading its default chart

  Scenario: The Periodicity control is present and matches the other pages
    Then a control labelled "Periodicity" is shown in the parameters bar
    And its options are exactly "day", "week", "month", "quarter" and "year", in that order

  Scenario: Selecting an interval redraws historical and projected series
    Given the user turns on the "5Y" return toggle
    And the user clicks the "10Y" horizon button
    When the user selects periodicity "quarter" on Projection
    Then the historical series and every projected series are plotted at one point per calendar quarter
    And the account, start date, target date and selected returns are unchanged

  Scenario: Selecting "day" requests the finest interval
    Given the user turns on the "5Y" return toggle
    And the user clicks the "10Y" horizon button
    When the user selects periodicity "day" on Projection
    Then the chart is requested at the "day" interval

  Scenario: The control is disabled while the chart refreshes
    Given the user clicks the "10Y" horizon button
    And the backing service now takes 3 seconds to answer chart requests
    When the user clicks the "20Y" horizon button without waiting for the chart
    Then the Periodicity buttons are disabled
    And the Periodicity buttons become enabled once the chart has loaded
