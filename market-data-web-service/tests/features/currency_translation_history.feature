Feature: Currency translation on historical security prices

  Scenario: Historical prices translated across the full requested date range
    Given AAPL has USD price history for 2025-01-02 at 185.50 and 2025-01-03 at 186.20
    And the USDGBP FX series has rate 0.7884 on 2025-01-02 and 0.7902 on 2025-01-03
    When a client requests AAPL history from 2025-01-02 to 2025-01-03 with currency "GBP"
    Then the response status code is 200
    And the response history currency is "GBP"
    And the entry for 2025-01-02 has close approximately 146.22 and fx_rate 0.7884
    And the entry for 2025-01-03 has close approximately 147.01 and fx_rate 0.7902

  Scenario: FX rate forward-filled when FX market is closed on a security trading day
    Given AAPL has USD price history for 2025-01-17 at 143.10 and 2025-01-20 at 144.50
    And the USDGBP FX series has only rate 0.7900 on 2025-01-17
    When a client requests AAPL history from 2025-01-17 to 2025-01-20 with currency "GBP"
    Then the response status code is 200
    And the entry for 2025-01-17 has fx_rate 0.7900
    And the entry for 2025-01-20 has fx_rate 0.7900

  Scenario: FX rate backward-filled when no prior rate exists
    Given AAPL has USD price history for 2025-01-02 at 145.88 and 2025-01-03 at 146.22
    And the USDGBP FX series has only rate 0.7895 on 2025-01-03
    When a client requests AAPL history from 2025-01-02 to 2025-01-03 with currency "GBP"
    Then the response status code is 200
    And the entry for 2025-01-02 has fx_rate 0.7895
    And the entry for 2025-01-03 has fx_rate 0.7895

  Scenario: No translation applied when native currency matches requested currency
    Given BARC.L has GBP price history for 2025-01-02 at 2.18 and 2025-01-03 at 2.20
    When a client requests BARC.L history from 2025-01-02 to 2025-01-03 with currency "GBP"
    Then the response status code is 200
    And the response history currency is "GBP"
    And all entries have null fx_rate
