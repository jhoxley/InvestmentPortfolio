Feature: Local price file fallback — current price

  Scenario: Current price served from local fallback file
    Given the primary data source returns no current price for ticker "PRIV01"
    And a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"
    And the most recent entry in the local file is "2025-01-06" at 150.00
    When a consumer requests the current price for "PRIV01"
    Then the response status is 200
    And the response price is 150.00
    And the response currency is "GBP"
    And the response as-of date is "2025-01-06"
    And the response market status is "closed"

  Scenario: Current price fallback ticker with no configuration returns not-found error
    Given the primary data source returns no current price for ticker "UNKNOWN"
    And no fallback configuration exists for "UNKNOWN"
    When a consumer requests the current price for "UNKNOWN"
    Then the response status is 404
