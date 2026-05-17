Feature: Price series gap fill for security history

  Scenario: Mid-series gap is filled by forward-fill
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
    When a client requests price history from 2025-01-02 to 2025-01-06
    Then the response contains 3 price entries
    And the entry for 2025-01-03 has close price 100.00
    And the entry for 2025-01-06 has close price 102.00

  Scenario: Multiple consecutive gaps are all forward-filled
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-07 at 105.00
    When a client requests price history from 2025-01-02 to 2025-01-07
    Then the response contains 4 price entries
    And the entries for 2025-01-03 and 2025-01-06 both have close price 100.00

  Scenario: End-of-range gap is filled forward to requested end date
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-03 at 98.00
    When a client requests price history from 2025-01-02 to 2025-01-07
    Then the response contains 4 price entries
    And the entries for 2025-01-06 and 2025-01-07 both have close price 98.00

  Scenario: Start of range precedes first observation — back-fill applied
    Given the data source has no price before 2025-01-06
    When a client requests price history from 2025-01-02 to 2025-01-07
    Then the response contains 4 price entries
    And the entries for 2025-01-02 and 2025-01-03 both have close price 100.00

  Scenario: Data source only has observation for yesterday — today is forward-filled
    Given today is a business day
    And the data source has a price for yesterday at 100.00 but no price for today
    When a client requests price history ending today
    Then the response contains an entry for today
    And the entry for today has close price 100.00

  Scenario: Data source observation is two business days old — today is forward-filled
    Given today is a business day
    And the data source has a price for T-2 at 100.00 but no observations for T-1 or today
    When a client requests price history ending today
    Then the response contains entries for T-1 and today
    And both T-1 and today entries have close price 100.00
