Feature: Pence Unit Normalisation — Current Price

  Scenario: Current price for pence-denominated security is normalised to pounds
    Given the pricing source returns a price of 31140 in currency "GBp" for ticker "CNKY.L"
    When a consumer requests the current price for "CNKY.L"
    Then the response status code is 200
    And the pence response currency is "GBP"
    And the pence response price is 311.40

  Scenario: Current price for a non-sub-unit currency is returned unchanged
    Given the pricing source returns a price of 150.00 in currency "USD" for ticker "AAPL"
    When a consumer requests the current price for "AAPL"
    Then the response status code is 200
    And the pence response currency is "USD"
    And the pence response price is 150.00

  Scenario: Current price for US cent-denominated security is normalised to dollars
    Given the pricing source returns a price of 15000 in currency "USd" for a ticker
    When a consumer requests the current price for that ticker
    Then the response status code is 200
    And the pence response currency is "USD"
    And the pence response price is 150.00

  Scenario: Current price in major-unit GBP is not normalised
    Given the pricing source returns a price of 311.40 in currency "GBP" for a ticker
    When a consumer requests the current price for that ticker
    Then the response status code is 200
    And the pence response currency is "GBP"
    And the pence response price is 311.40

  Scenario: Variant casing of sub-unit currency code is still normalised
    Given the pricing source returns a price of 31140 in currency "gBp" for a ticker
    When a consumer requests the current price for that ticker
    Then the response status code is 200
    And the pence response currency is "GBP"
    And the pence response price is 311.40
