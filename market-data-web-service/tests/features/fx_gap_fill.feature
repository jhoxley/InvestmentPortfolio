Feature: FX pair history gap fill

  Scenario: FX pair history contains a rate for every business day in range
    Given the FX provider returns rates for GBPUSD on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only
    When a client requests GBPUSD history from 2025-01-02 to 2025-01-06
    Then the FX response contains 3 rate entries
    And the rate for 2025-01-03 is 1.25
