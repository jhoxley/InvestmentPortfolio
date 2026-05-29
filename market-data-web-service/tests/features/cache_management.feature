Feature: Cache management — delete individual or all cache entries

  # --- User Story 4: Delete Single Ticker Cache ---

  Scenario: Delete cache for an existing ticker
    Given a cache file exists for ticker "AAPL"
    When an operator calls DELETE /cache/AAPL
    Then the response status code is 200
    And the response confirms the entry was deleted
    And the cache file for "AAPL" is removed

  Scenario: Delete cache for a ticker with no existing cache
    Given no cache file exists for ticker "XYZ"
    When an operator calls DELETE /cache/XYZ
    Then the response status code is 200
    And the response indicates no cache was found

  # --- User Story 5: Clear Entire Cache ---

  Scenario: Clear all cache entries when cache contains data
    Given cache files exist for tickers "AAPL", "MSFT", and "TSLA"
    When an operator calls DELETE /cache
    Then the response status code is 200
    And the response confirms 3 entries were deleted
    And all cache files are removed

  Scenario: Clear all cache entries when cache is empty
    Given no cache files exist
    When an operator calls DELETE /cache
    Then the response status code is 200
    And the response confirms 0 entries were deleted
