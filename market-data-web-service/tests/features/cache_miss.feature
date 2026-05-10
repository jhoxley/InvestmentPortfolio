Feature: Cache miss — fetch from YFinance and populate the cache

  Scenario: No cache exists for requested ticker
    Given no cache file exists for ticker "GOOG"
    And YFinance returns data for "GOOG" from "2025-01-02" to "2025-03-31"
    When a consumer requests price history for "GOOG" from "2025-01-02" to "2025-03-31"
    Then the response status code is 200
    And the full date range is fetched from YFinance
    And a cache file is created for "GOOG"
    And the response contains the correct price data
