Feature: Local price file fallback — FX currency conversion

  Scenario: Local fallback prices are converted to the requested target currency
    Given the primary data source returns no price history for ticker "PRIV01"
    And a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"
    And the local file contains a price of 100.00 on "2025-01-02"
    And the FX rate for GBPUSD on "2025-01-02" is 1.25
    When a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-02" with currency "USD"
    Then the response price for "2025-01-02" is 125.00
    And the response currency is "USD"
