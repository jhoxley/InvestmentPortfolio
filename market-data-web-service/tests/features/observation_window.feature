Feature: Observation window reported on price history responses

  Scenario: Observation window reported in observed-only mode
    Given a cache file exists for ticker "AAPL" covering 2024-03-01 to 2025-06-30
    When a consumer requests observed-only history for "AAPL" from 2025-01-02 to 2025-01-31
    Then the response status code is 200
    And the response reports first observed date 2024-03-01
    And the response reports last observed date 2025-06-30

  Scenario: Observation window reported in default gap-filled mode
    Given a cache file exists for ticker "AAPL" covering 2024-03-01 to 2025-06-30
    When a consumer requests default history for "AAPL" from 2025-01-02 to 2025-01-31
    Then the response status code is 200
    And the response contains an entry for every business day from 2025-01-02 to 2025-01-31
    And the response reports first observed date 2024-03-01
    And the response reports last observed date 2025-06-30

  Scenario: Observation window reflects the instrument not the requested range
    Given a cache file exists for ticker "AAPL" covering 2024-03-01 to 2025-06-30
    When a consumer requests default history for "AAPL" from 2025-05-01 to 2025-05-30
    Then the reported first observed date is earlier than the requested start date
    And the reported last observed date is later than the requested end date

  Scenario: Observation window widens after a request extends the known history
    Given a cache file exists for ticker "AAPL" covering 2024-03-01 to 2025-06-30
    And the data source returns observations for "AAPL" starting 2023-02-15
    When a consumer requests default history for "AAPL" from 2023-01-02 to 2023-12-29
    Then the response reports first observed date 2023-02-15
    When a consumer requests default history for "AAPL" from 2025-01-02 to 2025-01-31
    Then the response reports first observed date 2023-02-15

  Scenario: Observation window is reported for a local-only fallback instrument
    Given a local-only fallback file for "PRIV01" contains rows from 2022-01-03 to 2024-12-31
    When a consumer requests observed-only history for "PRIV01" from 2022-01-03 to 2024-12-31
    Then the response status code is 200
    And the response reports first observed date 2022-01-03
    And the response reports last observed date 2024-12-31

  Scenario: Observation window is reported when the fallback file was triggered by an empty primary source
    Given a fallback file for "PRIV01" contains rows from 2022-01-03 to 2024-12-31 and is not local-only
    And the primary data source returns no observations for "PRIV01"
    When a consumer requests default history for "PRIV01" from 2022-01-03 to 2024-12-31
    Then the response status code is 200
    And the response reports first observed date 2022-01-03
    And the response reports last observed date 2024-12-31

  Scenario: Existing response fields are unchanged by the additive window fields
    Given a cache file exists for ticker "AAPL" covering 2024-03-01 to 2025-06-30
    When a consumer requests default history for "AAPL" from 2025-01-02 to 2025-01-31
    Then the response contains the ticker, currency and prices fields
    And each price entry contains only the date, close and fx_rate fields
    And the response contains exactly the two observation window fields in addition
