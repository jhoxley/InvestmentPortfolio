Feature: Pence Unit Normalisation — FX Conversion Ordering

  Scenario: Pence-quoted history converted to a third currency applies normalisation first
    Given the pricing source returns "GBp" history with raw close 31140 on 2026-05-22
    And an FX rate of 1.25 from GBP to USD exists for 2026-05-22
    When a consumer requests pence-quoted history with currency "USD" on 2026-05-22
    Then the response status code is 200
    And the fx history response currency is "USD"
    And the fx history close on 2026-05-22 is 389.25

  Scenario: Current price for pence-quoted ticker with currency conversion
    Given the pricing source returns a current price of 31140 in currency "GBp"
    And an FX rate of 1.25 from GBP to USD exists for 2026-05-22
    When a consumer requests the current price for that ticker with currency "USD"
    Then the response status code is 200
    And the fx response currency is "USD"
    And the fx response price is 389.25
