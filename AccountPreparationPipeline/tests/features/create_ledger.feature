Feature: Ledger Running Balance
  As a user with a consolidated investment journal
  I want to generate a position ledger with cumulative running balances
  So that I can see the net cost and holding size of each position over time

  Scenario: Buy events produce negated cumulative value and positive cumulative quantity
    Given a consolidated journal with two buy events for the same position
    When I run create_ledger
    Then the exit code is 0
    And the first output row value equals the negated first buy value
    And the second output row value equals the negated sum of both buy values
    And the second output row quantity equals the sum of both buy quantities

  Scenario: Sell events negate both value and quantity in cumulation
    Given a consolidated journal with a buy followed by a sell for the same position
    When I run create_ledger
    Then the exit code is 0
    And the final output row quantity equals the buy quantity minus the sell quantity
    And the final output row value equals the negated buy value minus the negated sell value

  Scenario: Cash rows with blank quantity use value as quantity for cumulation
    Given a consolidated journal with two Cash deposit events with blank quantity
    When I run create_ledger
    Then the exit code is 0
    And the final Cash row value equals the sum of both deposit values
    And the final Cash row quantity equals the sum of both deposit values

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
