Feature: Currency conversion uses gap-filled FX rates — no spikes from missing rates

  Scenario: Currency conversion uses gap-filled FX rates — no spikes from missing rates
    Given the provider returns security prices for 2025-01-02, 2025-01-03, and 2025-01-06 all at 100.00
    And the FX provider returns rates for USDGBP on 2025-01-02 at 1.25 and 2025-01-06 at 1.27 only
    When a client requests AAPL history from 2025-01-02 to 2025-01-06 with currency GBP
    Then the conversion response contains 3 price entries
    And the entry for 2025-01-03 has a non-zero close
    And the entry for 2025-01-03 close price equals 125.00
