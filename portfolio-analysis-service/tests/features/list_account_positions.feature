Feature: List Account Positions

  @us2
  Scenario: Enumerate all positions held in an account
    Given account "test-portfolio" has an ingested position ladder containing positions "Apple Inc", "Cash", and "Sold Corp"
    When a request is made to the positions endpoint for account "test-portfolio"
    Then the response status is 200
    And all three positions appear, each with its own first and last recorded date
    And the response body includes a "_links.self" URL

  @us2
  Scenario: Unknown account name is rejected
    Given no resource of any kind has been ingested for account "unknown-account"
    When a request is made to the positions endpoint for account "unknown-account"
    Then the response status is 404

  @us2
  Scenario: A known account with no ingested position ladder is rejected, but not as unknown
    Given account "capital-only-portfolio" has an ingested capital ledger but no position ladder
    When a request is made to the positions endpoint for account "capital-only-portfolio"
    Then the response status is 422
