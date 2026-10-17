Feature: Observed-only price history from local fallback files

  Scenario: Observed-only history returns the fallback file's raw rows in range
    Given a local-only fallback file for "PRIV01" with rows on 2025-01-02, 2025-01-06 and 2025-01-09
    When a consumer requests observed-only history for "PRIV01" from 2025-01-02 to 2025-01-09
    Then the response status code is 200
    And the response contains exactly 3 price entries
    And the returned dates are 2025-01-02, 2025-01-06 and 2025-01-09

  Scenario: Fallback file rows outside the requested range are excluded
    Given a local-only fallback file for "PRIV01" with rows on 2025-01-02, 2025-01-06 and 2025-01-09
    When a consumer requests observed-only history for "PRIV01" from 2025-01-05 to 2025-01-07
    Then the response status code is 200
    And the response contains exactly 1 price entry
    And the returned date is 2025-01-06

  Scenario: Default mode still gap-fills fallback file data
    Given a local-only fallback file for "PRIV01" with rows on 2025-01-02, 2025-01-06 and 2025-01-09
    When a consumer requests default history for "PRIV01" from 2025-01-02 to 2025-01-09
    Then the response status code is 200
    And the response contains an entry for every business day from 2025-01-02 to 2025-01-09
