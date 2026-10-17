Feature: Position and Portfolio-Weighted Daily Returns

  @us1
  Scenario: Daily position return reflects price change and income
    Given a priced position ladder for account "test-portfolio" with sub-account "Equities A" active on consecutive business days 2024-01-02 through 2024-01-05
    And "Equities A" has price 100.0 on 2024-01-02, 102.0 on 2024-01-03, 101.0 on 2024-01-04, and 103.0 on 2024-01-05
    And "Equities A" has total_income 0.0 through 2024-01-03, then 5.0 from 2024-01-04 onward, with quantity 10.0 on every date
    When the ladder is ingested
    Then the row for 2024-01-03 has position_return equal to (102.0 - 100.0 + 0.0) / 100.0
    And the row for 2024-01-04 has position_return equal to (101.0 - 102.0 + 0.5) / 102.0
    And the row for 2024-01-05 has position_return equal to (103.0 - 101.0 + 0.0) / 101.0
    And every row in the stored ladder has a non-null position_return and weighted_position_return

  @us1
  Scenario: First recorded date for a position has zero return
    Given a priced position ladder for account "test-portfolio" with sub-account "Equities B" first appearing on 2024-02-01 (no prior row exists for "Equities B")
    When the ladder is ingested
    Then the row for "Equities B" on 2024-02-01 has position_return equal to 0.0

  @us2
  Scenario: Weighted return uses the previous date's (start-of-day) portfolio weight
    Given a priced position ladder for account "test-portfolio-us2" with sub-accounts "Equities A" and "Equities B" both present on 2024-03-04 and 2024-03-05
    And on 2024-03-04, "Equities A" has quantity 55.0 and "Equities B" has quantity 45.0, both priced at 100.0
    And on 2024-03-05, "Equities A" has price 102.0 and quantity 60.0, and "Equities B" has price 99.0 and quantity 40.0
    When the ladder is ingested
    Then the portfolio_weight for "Equities A" differs between 2024-03-04 and 2024-03-05
    And the "Equities A" row for 2024-03-05 has weighted_position_return equal to its position_return multiplied by its 2024-03-04 portfolio_weight, not its 2024-03-05 portfolio_weight
    And the "Equities B" row for 2024-03-05 has weighted_position_return equal to its position_return multiplied by its 2024-03-04 portfolio_weight, not its 2024-03-05 portfolio_weight

  @us2
  Scenario: First recorded date for a position has zero weighted return
    Given a priced position ladder for account "test-portfolio" with sub-account "Equities B" first appearing on 2024-02-01 (no prior row exists for "Equities B")
    When the ladder is ingested
    Then the row for "Equities B" on 2024-02-01 has weighted_position_return equal to 0.0

  @us3
  Scenario: Returns are stable across repeated reads without re-ingestion
    Given a priced and return-enriched position ladder already ingested for account "test-portfolio-us3"
    When the position time series is retrieved twice in a row for the same account, positions, attributes, and date range
    Then both responses report identical position_return and weighted_position_return values for every matching row
