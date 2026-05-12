Feature: Currency translation on current security price

  Scenario: Current price returned in native currency when no target currency specified
    Given AAPL is a USD security with current price 185.50
    When a client requests the current price for "AAPL" with no currency parameter
    Then the response status code is 200
    And the response currency is "USD"
    And the response price is 185.50
    And the response fx_rate is null

  Scenario: Current price translated to requested target currency
    Given AAPL is a USD security with current price 185.50
    And the USDGBP FX rate is 0.7912
    When a client requests the current price for "AAPL" with currency "GBP"
    Then the response status code is 200
    And the response currency is "GBP"
    And the response price is approximately 146.72
    And the response fx_rate is 0.7912

  Scenario: No translation applied when requested currency matches native currency
    Given BARC.L is a GBP security with current price 2.18
    When a client requests the current price for "BARC.L" with currency "GBP"
    Then the response status code is 200
    And the response currency is "GBP"
    And the response price is 2.18
    And the response fx_rate is null

  Scenario: Invalid currency code returns a validation error
    Given AAPL is a USD security with current price 185.50
    When a client requests the current price for "AAPL" with currency "INVALID"
    Then the response status code is 422
    And the response error code is "INVALID_CURRENCY"
