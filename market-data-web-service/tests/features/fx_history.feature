Feature: FX pair rate history endpoint

  Scenario: FX pair history returned for a valid currency pair and date range
    Given the USDGBP FX cache has no data
    And the provider has USDGBP rates 0.7884 on 2025-01-02 and 0.7902 on 2025-01-03
    When a client requests FX history for "USDGBP" from 2025-01-02 to 2025-01-03
    Then the FX response status code is 200
    And the FX response pair is "USDGBP"
    And the FX response base_currency is "USD"
    And the FX response quote_currency is "GBP"
    And the FX rates list has 2 entries
    And the FX rate on 2025-01-02 is 0.7884
    And the FX rate on 2025-01-03 is 0.7902

  Scenario: FX pair history served from cache on repeated request
    Given the USDGBP FX cache has rates 0.7884 on 2025-01-02 and 0.7902 on 2025-01-03
    When a client requests FX history for "USDGBP" from 2025-01-02 to 2025-01-03
    Then the FX response status code is 200
    And the FX rates list has 2 entries
    And the mock FX provider was not called

  Scenario: Invalid ISO currency code in pair returns a validation error
    When a client requests FX history for "USDZZ" from 2025-01-02 to 2025-01-03
    Then the FX response status code is 422

  Scenario: Start date after end date returns a validation error
    When a client requests FX history for "USDGBP" from 2025-03-31 to 2025-01-02
    Then the FX response status code is 422
