Feature: Partial cache hit — fetch only missing segments from YFinance

  Scenario: Request extends beyond the start of cached data
    Given a cache file exists for ticker "MSFT" covering dates "2025-03-03" to "2025-06-30"
    And YFinance returns data for "MSFT" from "2025-01-02" to "2025-02-28"
    When a consumer requests price history for "MSFT" from "2025-01-02" to "2025-06-30"
    Then the response status code is 200
    And the response covers the full requested range
    And YFinance was called exactly once for the before segment
    And the cache is updated to include the newly fetched data

  Scenario: Request extends beyond the end of cached data
    Given a cache file exists for ticker "MSFT" covering dates "2025-01-02" to "2025-06-30"
    And YFinance returns data for "MSFT" from "2025-07-01" to "2025-09-30"
    When a consumer requests price history for "MSFT" from "2025-01-02" to "2025-09-30"
    Then the response status code is 200
    And the response covers the full requested range
    And YFinance was called exactly once for the after segment
    And the cache is updated to include the newly fetched data

  Scenario: Request extends beyond both ends of cached data
    Given a cache file exists for ticker "TSLA" covering dates "2025-04-01" to "2025-06-30"
    And YFinance returns data for "TSLA" from "2025-01-02" to "2025-03-31"
    And YFinance also returns data for "TSLA" from "2025-07-01" to "2025-09-30"
    When a consumer requests price history for "TSLA" from "2025-01-02" to "2025-09-30"
    Then the response status code is 200
    And the response covers the full requested range
    And YFinance was called twice for both segments
    And the cache is updated to include the newly fetched data

  Scenario: YFinance fails when fetching a missing segment
    Given a cache file exists for ticker "MSFT" covering dates "2025-01-02" to "2025-06-30"
    And YFinance is unavailable
    When a consumer requests price history for "MSFT" from "2025-01-02" to "2025-09-30"
    Then the response status code is 503
    And the existing cache entry for "MSFT" is unchanged
