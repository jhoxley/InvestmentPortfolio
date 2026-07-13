Feature: Account Time Series

  @us1
  Scenario: Retrieve a time series for a known account and valid attributes
    Given account "test-portfolio" has an ingested capital ledger and position ladder
    When a request is made for attributes "capital" and "market_value" from 2024-01-02 to 2024-01-10
    Then the response status is 200
    And the response contains one entry per business day from 2024-01-02 to 2024-01-10
    And every entry contains a "capital" value and a "market_value" value
    And the response body includes "_links.self", "_links.attributes", and "_links.accounts" URLs

  @us1
  Scenario: Underlying data older than today is forward-filled, not treated as an error
    Given account "test-portfolio" has a capital ledger whose latest recorded date is before today
    When a request is made for attribute "capital" ending on the most recent business day
    Then the response status is 200
    And entries after the capital ledger's latest recorded date carry the last recorded value

  @us1
  Scenario: Requesting an attribute whose required source was never ingested is rejected
    Given account "ladder-only-portfolio" has an ingested position ladder but no capital ledger
    When a request is made for attribute "capital"
    Then the response status is 422
    And the response identifies that the capital ledger source is missing for this account

  @us1
  Scenario: Missing mandatory attribute is rejected
    Given account "test-portfolio" has an ingested capital ledger and position ladder
    When a request is made with no attribute specified
    Then the response status is 422

  @us1
  Scenario: Unknown account name is rejected
    Given no ledger of any kind has been ingested for account "unknown-account"
    When a request is made for attribute "capital" for account "unknown-account"
    Then the response status is 404

  @us1
  Scenario: Start date after end date is rejected
    Given account "test-portfolio" has an ingested capital ledger and position ladder
    When a request is made with start date 2024-02-01 and end date 2024-01-01
    Then the response status is 422

  @us1
  Scenario: End date in the future is rejected
    Given account "test-portfolio" has an ingested capital ledger and position ladder
    When a request is made with an end date after today
    Then the response status is 422

  @us1
  Scenario: Non-business-day start and end dates are silently adjusted
    Given account "test-portfolio" has an ingested capital ledger and position ladder
    When a request is made with a start date that falls on a Saturday
    Then the response status is 200
    And the first entry in the response is dated on or after the following Monday
