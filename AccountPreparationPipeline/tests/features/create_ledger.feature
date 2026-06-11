Feature: Ledger Running Balance
  As a user with a consolidated investment journal
  I want to generate a position ledger with cumulative running balances
  So that I can see the net cost and holding size of each position over time

  Scenario: Buy events produce negated cumulative Account Value and positive cumulative Account Quantity
    Given a consolidated journal with two buy events for the same position
    When I run create_ledger
    Then the exit code is 0
    And the first output row Account Value equals the negated first buy value
    And the second output row Account Value equals the negated sum of both buy values
    And the second output row Account Quantity equals the sum of both buy quantities

  Scenario: Sell events negate both Account Value and Account Quantity in cumulation
    Given a consolidated journal with a buy followed by a sell for the same position
    When I run create_ledger
    Then the exit code is 0
    And the final output row Account Quantity equals the buy quantity minus the sell quantity
    And the final output row Account Value equals the negated buy value minus the negated sell value

  Scenario: Cash rows with blank quantity use value as quantity for cumulation
    Given a consolidated journal with two Cash deposit events with blank quantity
    When I run create_ledger
    Then the exit code is 0
    And the final Cash row Account Value equals the sum of both deposit values
    And the final Cash row Account Quantity equals the sum of both deposit values

  Scenario: Running totals are independent per position
    Given a consolidated journal with events for two different positions
    When I run create_ledger
    Then the exit code is 0
    And each position accumulates independently

  Scenario: Output row count equals input row count
    Given a consolidated journal with 5 events
    When I run create_ledger
    Then the exit code is 0
    And the output has exactly 5 rows

  Scenario: Action and reference columns are unchanged in output
    Given a consolidated journal with buy and sell events
    When I run create_ledger
    Then the exit code is 0
    And the action column values in the output match the input
    And the reference column values in the output match the input

  Scenario: Missing input file returns exit code 2
    Given the input file does not exist
    When I run create_ledger
    Then the exit code is 2

  Scenario: Single buy produces Transaction Value equal to Account Value
    Given a consolidated journal with a single buy event
    When I run create_ledger
    Then the exit code is 0
    And the first row Transaction Value equals the first row Account Value

  Scenario: Second buy produces Transaction Value equal to the row delta
    Given a consolidated journal with two buy events for the same position
    When I run create_ledger
    Then the exit code is 0
    And the second row Transaction Value equals the negated second buy value
    And the second row Account Value equals the negated sum of both buy values

  Scenario: Sell row Transaction Value reflects the sell contribution
    Given a consolidated journal with a buy followed by a sell for the same position
    When I run create_ledger
    Then the exit code is 0
    And the sell row Transaction Value equals the negated sell value
    And the sell row Account Value satisfies the invariant

  Scenario: Transaction columns are independent per position
    Given a consolidated journal with events for two different positions
    When I run create_ledger
    Then the exit code is 0
    And each position Transaction Value equals its Account Value

  Scenario: Output contains exactly ten columns in defined order
    Given a consolidated journal with a single buy event
    When I run create_ledger
    Then the exit code is 0
    And the output has exactly ten columns in the defined order

  Scenario: First-time run produces Transaction ID column with sequential IDs
    Given a consolidated journal with a single buy event
    When I run create_ledger
    Then the exit code is 0
    And the Transaction ID column exists and first row value is 00001-001

  Scenario: Transaction IDs are sequential with 001 suffix on first run
    Given a consolidated journal with 3 events on different dates
    When I run create_ledger
    Then the exit code is 0
    And the Transaction IDs are 00001-001 00002-001 00003-001 in ascending row order

  Scenario: Same-date Cash offsets are ordered by reference to preserve per-position invariant
    Given a journal with two same-date buys and their Cash offsets
    When I run create_ledger
    Then the exit code is 0
    And the Cash rows in Transaction ID order satisfy the per-position invariant

  Scenario: Re-running with a new row between existing rows assigns suffix-incremented ID
    Given an existing ledger produced from a 3-row journal
    And a new journal event inserted between the first and second existing rows
    When I run create_ledger
    Then the exit code is 0
    And the original three IDs are unchanged and the new row gets 00001-002

  Scenario: Idempotent re-run produces identical Transaction IDs
    Given an existing ledger produced from a 3-row journal
    When I run create_ledger
    Then the exit code is 0
    And all Transaction IDs are identical to the prior run

  Scenario: New row after all existing rows gets next sequential prefix
    Given an existing ledger produced from a 3-row journal
    And a new journal event appended after all existing rows
    When I run create_ledger
    Then the exit code is 0
    And the new row gets Transaction ID 00004-001
