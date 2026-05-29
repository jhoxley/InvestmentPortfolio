Feature: Local price file fallback — price history

  Scenario: Price history served from local fallback file when primary source returns no data
    Given the primary data source returns no price history for ticker "PRIV01"
    And a fallback configuration maps "PRIV01" to a local CSV file with currency "GBP"
    And the local CSV file contains prices for "2025-01-02" and "2025-01-06"
    When a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-06"
    Then the response status is 200
    And the response currency is "GBP"
    And the response contains 3 price entries (gap-filled Mon-Fri series)
    And the response does not come from the price cache

  Scenario: Price history from local fallback with gap-fill applied
    Given the primary data source returns no price history for ticker "PRIV01"
    And a fallback configuration maps "PRIV01" to a local CSV file with 2 observations spanning 5 business days
    When a consumer requests price history for "PRIV01" over that 5-day range
    Then the response contains entries for all 5 business days
    And the gaps are filled by forward carry of the nearest observation

  Scenario: Ticker with no primary data and no fallback configuration returns not-found error
    Given the primary data source returns no price history for ticker "UNKNOWN"
    And no fallback configuration exists for "UNKNOWN"
    When a consumer requests price history for "UNKNOWN"
    Then the response status is 404

  Scenario: Price history for an ISIN-keyed fallback entry served via pseudo-ticker
    Given the primary data source has no ticker translation for ISIN "GB00B0PRVT01"
    And a fallback configuration maps "GB00B0PRVT01" to a local CSV file with currency "GBP"
    And the identifier-resolution endpoint is called for "GB00B0PRVT01"
    Then the resolution response returns "GB00B0PRVT01" as the ticker
    When a consumer requests price history for "GB00B0PRVT01"
    Then the response status is 200
    And the response contains prices from the local file

  Scenario: Fallback file with GBp currency is normalised to GBP before returning
    Given a fallback configuration maps "PRIV01" to a local CSV file with currency "GBp"
    When a consumer requests price history for "PRIV01" from "2025-01-02" to "2025-01-06"
    Then the response status is 200
    And the response currency is "GBP"
    And the pence prices are divided by 100

  Scenario: use_local_only flag bypasses primary source entirely
    Given a fallback configuration maps "PRIV01" to a local CSV file with use_local_only set
    When a consumer requests price history for "PRIV01"
    Then the primary data source is never queried
    And the response status is 200 with prices from the local file
