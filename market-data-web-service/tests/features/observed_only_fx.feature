Feature: Currency-converted observed-only price history

  Scenario: Observed-only prices converted at each observation's own date rate
    Given a USD security has observations on 2025-01-02 and 2025-01-06 only
    And the FX rate differs between 2025-01-02 and 2025-01-06
    When a consumer requests observed-only history in GBP from 2025-01-02 to 2025-01-06
    Then the response status code is 200
    And the response currency is "GBP"
    And the response contains exactly 2 price entries
    And each entry's price reflects the FX rate for its own date

  Scenario: A missing exchange rate on an observation date does not drop the observation
    Given a USD security has observations on 2025-01-02 and 2025-01-06 only
    And the FX source has no rate for 2025-01-06
    When a consumer requests observed-only history in GBP from 2025-01-02 to 2025-01-06
    Then the response status code is 200
    And the response contains exactly 2 price entries
    And the entry for 2025-01-06 is present with a carried forward FX rate

  Scenario: Currency conversion does not reintroduce non-observed dates
    Given a USD security has observations on 2025-01-02 and 2025-01-06 only
    And the FX source has rates for every business day from 2025-01-02 to 2025-01-08
    When a consumer requests observed-only history in GBP from 2025-01-02 to 2025-01-08
    Then the response status code is 200
    And the response contains exactly 2 price entries
    And the returned dates are 2025-01-02 and 2025-01-06
