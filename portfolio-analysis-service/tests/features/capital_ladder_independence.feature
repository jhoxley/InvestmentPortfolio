Feature: Capital Ledger and Position Ladder Independence

  @validation
  Scenario: Ingesting a capital ledger does not affect an existing position ladder for the same account
    Given a position ladder has been stored for account "cross-resource-a"
    When a capital ledger is ingested for account "cross-resource-a"
    Then the position ladder for "cross-resource-a" is unchanged
    And the capital ledger for "cross-resource-a" is retrievable

  @validation
  Scenario: Ingesting a position ladder does not affect an existing capital ledger for the same account
    Given a capital ledger has been stored for account "cross-resource-b"
    When a position ladder is ingested for account "cross-resource-b"
    Then the capital ledger for "cross-resource-b" is unchanged
    And the position ladder for "cross-resource-b" is retrievable
