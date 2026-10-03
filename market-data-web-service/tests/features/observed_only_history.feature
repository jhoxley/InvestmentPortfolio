Feature: Observed-only price history (fill=none)

  Scenario: Observed-only mode omits non-trading days
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
    When a consumer requests observed-only price history from 2025-01-02 to 2025-01-06
    Then the response status code is 200
    And the response contains exactly 2 price entries
    And the response contains an entry for 2025-01-02 with close price 100.00
    And the response contains an entry for 2025-01-06 with close price 102.00
    And the response contains no entry for 2025-01-03

  Scenario: Observed-only mode does not back-fill before the first observation
    Given the data source has no price before 2025-01-06
    When a consumer requests observed-only price history from 2025-01-02 to 2025-01-07
    Then the response status code is 200
    And the response contains no entry for 2025-01-02
    And the response contains no entry for 2025-01-03
    And the earliest entry in the response is 2025-01-06

  Scenario: Observed-only mode does not forward-fill a stale end of range
    Given today is a business day
    And the data source has a price for T-2 at 100.00 but no observations for T-1 or today
    When a consumer requests observed-only price history ending today
    Then the response status code is 200
    And the response contains no entry for today
    And the response contains no entry for the previous business day
    And the latest entry in the response is T-2

  Scenario: Default behaviour is unchanged when fill is not supplied
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
    When a consumer requests price history from 2025-01-02 to 2025-01-06 with no fill parameter
    Then the response status code is 200
    And the response contains exactly 3 price entries
    And the response contains an entry for 2025-01-03 with close price 100.00

  Scenario: Explicit fill all matches the default behaviour exactly
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
    When a consumer requests the same range once with fill all and once with no fill parameter
    Then both responses contain an identical list of price entries

  Scenario: Unrecognised fill value is rejected
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
    When a consumer requests price history with fill "forward"
    Then the response status code is 422
    And the error identifies "fill" as the invalid parameter
    And the data source was never called

  Scenario: Observed-only mode never labels a filled price as an observation
    Given the data source has observations on only 2 of the 5 business days in the range
    When a consumer requests observed-only price history from 2025-01-02 to 2025-01-08
    Then the response status code is 200
    And the response contains exactly 2 price entries
    And every returned date is present in the data source observations

  Scenario: The fill parameter has no effect on other endpoints
    Given the data source has prices for 2025-01-02 at 100.00 and 2025-01-06 at 102.00
    When a consumer requests the current price with and without fill none
    Then both current price responses are identical apart from their timestamps
    When a consumer requests FX history with and without fill none
    Then both FX history responses are identical
