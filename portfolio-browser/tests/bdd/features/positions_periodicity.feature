Feature: Periodicity control on Positions
  As a user comparing individual positions
  I want the same Periodicity control available on Positions
  So that a Positions chart can be read alongside an Overview chart at a matching interval (spec 021)

  Scenario: Positions offers an identical Periodicity control
    Given portfolio-analysis-service has multiple accounts with position data
    And the Positions page has finished loading its default view
    Then a control labelled "Periodicity" is shown in the parameters bar
    And its options are exactly "day", "week", "month", "quarter" and "year", in that order

  Scenario: Selecting a periodicity aggregates every plotted position
    Given portfolio-analysis-service has an account with two positions with data across 2025
    And the Positions page has finished loading its default view
    And the user sets the date range to 2025-01-01 through 2025-12-31
    When the user selects periodicity "quarter" on Positions
    Then each position's series is plotted at one point per calendar quarter
    And the positions plotted, the selected attributes and the date range are unchanged

  Scenario: Periodicity and the stacked-area view work together
    Given portfolio-analysis-service has an account with two positions with data across 2025
    And the Positions page has finished loading its default view
    And the user sets the date range to 2025-01-01 through 2025-12-31
    And the user turns "Stacked area graph" on
    When the user selects periodicity "month" on Positions
    Then the stacked chart redraws with one band segment per calendar month
    And no error or empty state is shown

  Scenario: Switching pages keeps each page's own periodicity behaviour intact
    Given portfolio-analysis-service has multiple accounts with position data
    And the Overview page has finished loading its default chart
    And the user selects periodicity "year"
    When the user clicks the "Positions" navigation item
    Then the Positions page shows its own Periodicity control in a valid state
    And its chart renders without error

  Scenario: An explicit choice is not overridden by a later date-range change on Positions
    Given portfolio-analysis-service has two accounts for periodicity stickiness checks
    And the Positions page has finished loading its default view
    And the user selects periodicity "month" on Positions
    When the user sets the date range to 2025-01-01 through 2025-03-31
    Then the active periodicity button is "month"

  Scenario: An explicit choice survives an account switch on Positions
    Given portfolio-analysis-service has two accounts for periodicity stickiness checks
    And the Positions page has finished loading its default view
    And the user selects periodicity "quarter" on Positions
    When the user selects account "PERIODICITY-POSITIONS-2"
    Then the active periodicity button is "quarter"
