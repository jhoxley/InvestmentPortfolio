Feature: Local price file fallback — zero-price handling

  Scenario: Zero prices in a use_local_only fallback file are served, not filtered
    Given a fallback configuration maps "PRIV01" to a local CSV file of all-zero prices with use_local_only set
    When a consumer requests the current price for "PRIV01"
    Then the response status is 200
    And the response price is 0.00

  Scenario: Zero prices in a triggered (non-use_local_only) fallback file are still filtered as bad data
    Given the primary data source returns no current price for ticker "PRIV01"
    And a fallback configuration maps "PRIV01" to a local CSV file of all-zero prices without use_local_only set
    When a consumer requests the current price for "PRIV01"
    Then the response status is 404
