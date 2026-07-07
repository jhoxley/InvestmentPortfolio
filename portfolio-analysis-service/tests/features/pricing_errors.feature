Feature: Fail Fast When GBP Prices Are Incomplete
  As a developer
  I want ingestion to fail loudly when prices cannot be resolved
  So that the stored ladder never silently has missing or wrong-currency prices

  @us3
  Scenario: Missing GBP price on a business day blocks ingestion
    Given a ledger for account "gap-portfolio" with sub-account "Equity A" active from a start date to today
    And the market data service has a gap in "Equity A"'s GBP price history
    When the ledger is ingested for account "gap-portfolio"
    Then the ingestion request fails with status 422
    And the error identifies "Equity A"
    And no position ladder is persisted or updated for "gap-portfolio"

  @us3
  Scenario: Missing identifier mapping blocks ingestion
    Given a ledger for account "unmapped-portfolio" with sub-account "Equity C"
    And the identifier mapping has no entry for "Equity C"
    When the ledger is ingested for account "unmapped-portfolio"
    Then the ingestion request fails with status 422
    And the error identifies "Equity C"
    And no position ladder is persisted or updated for "unmapped-portfolio"

  @us3
  Scenario: Multiple simultaneous problems are all reported together
    Given a ledger for account "multi-problem-portfolio" with sub-accounts "Equity A" and "Equity D"
    And the market data service has a gap in "Equity A"'s GBP price history
    And the identifier mapping has no entry for "Equity D"
    When the ledger is ingested for account "multi-problem-portfolio"
    Then the ingestion request fails with status 422
    And the error identifies both "Equity A" and "Equity D" in the same response
