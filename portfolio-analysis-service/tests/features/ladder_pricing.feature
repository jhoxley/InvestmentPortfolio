Feature: Ladder Market Data Enrichment
  As a developer
  I want the position ladder to carry price, market value, and portfolio weight
  So that I can use it directly for performance and allocation analysis

  @us1
  Scenario: Ingested ladder rows are enriched with price, market value, and weight
    Given a valid sub-account ledger for account "priced-portfolio" with sub-accounts "Equity A" and "Cash"
    And "Equity A" resolves via the identifier mapping to a ticker with a complete GBP price history
    When the ledger is ingested for account "priced-portfolio"
    Then every row in the stored ladder has a non-null price, market value, and portfolio weight
    And the Cash sub-account's price is 1.0 on every date
    And each row's market value equals its price multiplied by its quantity

  @us1
  Scenario: Portfolio weight sums to 1.0 on every date
    Given a successfully enriched position ladder for account "priced-portfolio" with multiple sub-accounts
    When the portfolio weight column is inspected
    Then for every distinct date in the ladder, the sum of portfolio weight across all sub-accounts on that date is approximately 1.0

  @us1
  Scenario: Re-submitting an unchanged ledger reports a refreshed status
    Given account "priced-portfolio" already has an enriched position ladder from a prior ingestion
    When the exact same ledger file is submitted again for account "priced-portfolio"
    Then the response status is 200
    And the response body contains status "refreshed"
    And the ladder's price, market value, and portfolio weight columns reflect newly recomputed values
