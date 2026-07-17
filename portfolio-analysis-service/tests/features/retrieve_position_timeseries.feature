Feature: Position Time Series

  @us1
  Scenario: Retrieve a time series for two named positions and valid attributes
    Given account "test-portfolio" has an ingested position ladder containing positions "Apple Inc" and "Berkshire Hathaway Class B (BRK.B)"
    When a request is made for attributes "market_value" and "quantity", for positions "Apple Inc" and "Berkshire Hathaway Class B (BRK.B)", from 2024-01-02 to 2024-01-10
    Then the response status is 200
    And the response contains one entry per business day per position in that range
    And every entry contains a "market_value" value and a "quantity" value
    And the response body includes "_links.self", "_links.positions", "_links.attributes", and "_links.accounts" URLs

  @us1
  Scenario: No position names supplied defaults to every position in the account
    Given account "test-portfolio" has an ingested position ladder containing positions "Apple Inc", "Cash", and "Berkshire Hathaway Class B (BRK.B)"
    When a request is made for attribute "market_value" with no position names specified
    Then the response status is 200
    And entries are present for all three positions, including "Cash"

  @us1
  Scenario: An unrecognised position name is silently ignored, not rejected
    Given account "test-portfolio" has an ingested position ladder containing position "Apple Inc" but no position named "Nonexistent Corp"
    When a request is made for attribute "market_value" for positions "Apple Inc" and "Nonexistent Corp"
    Then the response status is 200
    And entries are present only for "Apple Inc"
    And no error is returned on account of "Nonexistent Corp"

  @us1
  Scenario: Position names containing spaces and symbols are correctly matched
    Given account "test-portfolio" has an ingested position ladder containing position "Berkshire Hathaway Class B (BRK.B)"
    When a request is made with that position name percent-encoded in the query string
    Then the response status is 200
    And entries are present for "Berkshire Hathaway Class B (BRK.B)"

  @us1
  Scenario: The "capital" attribute is no longer valid on this endpoint
    Given account "test-portfolio" has an ingested position ladder
    When a request is made for attribute "capital"
    Then the response status is 422
    And the response identifies "capital" as an unsupported attribute for this endpoint

  @us1
  Scenario: A known account with no ingested position ladder is rejected, but not as unknown
    Given account "capital-only-portfolio" has an ingested capital ledger but no position ladder
    When a request is made for attribute "market_value" for account "capital-only-portfolio"
    Then the response status is 422
    And the response identifies the position ladder as the missing required source

  @us1
  Scenario: Unknown account name is rejected
    Given no resource of any kind has been ingested for account "unknown-account"
    When a request is made for attribute "market_value" for account "unknown-account"
    Then the response status is 404

  @us1
  Scenario: Every requested position name fails to match returns zero entries, not an error
    Given account "test-portfolio" has an ingested position ladder containing position "Apple Inc" but no position named "Nonexistent Corp" or "Also Missing"
    When a request is made for attribute "market_value" for positions "Nonexistent Corp" and "Also Missing"
    Then the response status is 200
    And the response contains zero entries

  @us1
  Scenario: Missing mandatory attribute is rejected
    Given account "test-portfolio" has an ingested position ladder
    When a request is made with no attribute specified
    Then the response status is 422

  @us1
  Scenario: Start date after end date is rejected
    Given account "test-portfolio" has an ingested position ladder
    When a request is made for attribute "market_value" with start date 2024-02-01 and end date 2024-01-01
    Then the response status is 422

  @us1
  Scenario: End date in the future is rejected
    Given account "test-portfolio" has an ingested position ladder
    When a request is made for attribute "market_value" with an end date after today
    Then the response status is 422

  @us1
  Scenario: A position that was fully divested before the resolved end date has no entries after its last active date
    Given account "test-portfolio" has an ingested position ladder in which position "Sold Corp" was fully divested several business days before the ladder's own to_date
    When a request is made for attribute "market_value" for position "Sold Corp" ending on the most recent business day
    Then the response status is 200
    And "Sold Corp" has no entries after its own last recorded (divestment) date

  @us1
  Scenario: A still-held position is forward-filled to the resolved end date when the ladder itself is stale
    Given account "test-portfolio" has an ingested position ladder in which position "Apple Inc" is still held as of the ladder's own to_date
    When a request is made for attribute "market_value" for position "Apple Inc" ending on the most recent business day
    Then the response status is 200
    And "Apple Inc" has entries through the resolved end date, with every entry after its last ingested date carrying the same forward-filled market_value
