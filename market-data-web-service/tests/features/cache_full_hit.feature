Feature: Full cache hit — serve history from cache without calling YFinance

  Scenario: Request is fully satisfied by cached data
    Given a cache file exists for ticker "AAPL" covering dates "2025-01-02" to "2025-03-31"
    When a consumer requests price history for "AAPL" from "2025-01-02" to "2025-03-31"
    Then the response status code is 200
    And the response prices list contains the cached entries
    And no external call to YFinance is made

  Scenario: Request for a sub-range of cached data uses cache only
    Given a cache file exists for ticker "AAPL" covering dates "2025-01-02" to "2025-12-31"
    When a consumer requests price history for "AAPL" from "2025-03-03" to "2025-06-30"
    Then the response status code is 200
    And the response prices list contains only entries within the requested range
    And no external call to YFinance is made
