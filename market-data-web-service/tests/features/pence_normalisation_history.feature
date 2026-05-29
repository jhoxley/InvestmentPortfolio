Feature: Pence Unit Normalisation — Price History

  Scenario: Historical prices for pence-denominated security are normalised
    Given the history source returns "GBp" prices for "CNKY.L" on 2026-05-20/21/22
    When a consumer requests price history for "CNKY.L" from 2026-05-20 to 2026-05-22
    Then the response status code is 200
    And the history response currency is "GBP"
    And the history close on 2026-05-20 is 310.00
    And the history close on 2026-05-21 is 311.00
    And the history close on 2026-05-22 is 311.40

  Scenario: Historical prices for a standard currency are returned unchanged
    Given the history source returns "EUR" prices for a ticker on 2026-05-20 and 2026-05-21
    When a consumer requests price history from 2026-05-20 to 2026-05-21
    Then the response status code is 200
    And the history response currency is "EUR"
    And the history close on 2026-05-20 is 100.00
    And the history close on 2026-05-21 is 101.00
