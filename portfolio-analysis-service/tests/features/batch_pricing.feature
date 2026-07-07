Feature: Efficient Batch Price Retrieval Per Sub-Account
  As a developer
  I want exactly one price-history request per distinct non-Cash sub-account
  So that enrichment never issues one API call per individual date

  @us2
  Scenario: One batch request per distinct non-Cash sub-account
    Given a ledger for account "batch-portfolio" with sub-account "Equity A" active over 60 business days
    When the ledger is ingested for account "batch-portfolio"
    Then exactly one price-history request is made for "Equity A"
    And no price-history request is made for the "Cash" sub-account

  @us2
  Scenario: Multiple sub-accounts each get their own single batch request
    Given a ledger for account "batch-portfolio-2" with sub-accounts "Equity A" and "Equity B" active over different ranges
    When the ledger is ingested for account "batch-portfolio-2"
    Then exactly one price-history request is made for "Equity A"
    And exactly one price-history request is made for "Equity B"
