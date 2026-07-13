Feature: List Ingested Accounts

  @us3
  Scenario: Enumerate accounts with both resources ingested
    Given account "test-portfolio" has an ingested capital ledger and position ladder
    When a request is made to the accounts endpoint
    Then the response status is 200
    And "test-portfolio" appears with its capital ledger date range and position ladder date range
    And the response body includes a "_links.self" URL

  @us3
  Scenario: Enumerate an account with only one resource ingested
    Given account "capital-only-portfolio" has an ingested capital ledger but no position ladder
    When a request is made to the accounts endpoint
    Then the response status is 200
    And "capital-only-portfolio" appears with a capital ledger date range and no position ladder range
