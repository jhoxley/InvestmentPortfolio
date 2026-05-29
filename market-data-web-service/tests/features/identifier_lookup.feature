Feature: Identifier-to-Ticker Lookup — Happy Path

  Scenario: ISIN resolves to a ticker
    Given the provider resolves "US0378331005" to ticker "AAPL" on exchange "NMS"
    When a client requests the ticker for "US0378331005"
    Then the identifier response status is 200
    And the response ticker is "AAPL"
    And the response identifier_type is "ISIN"
    And the response security_name is non-empty
    And the response exchange is non-empty

  Scenario: CUSIP resolves to a ticker
    Given the provider resolves "037833100" to ticker "AAPL" on exchange "NMS"
    When a client requests the ticker for "037833100"
    Then the identifier response status is 200
    And the response ticker is "AAPL"
    And the response identifier_type is "CUSIP"

  Scenario: SEDOL resolves to a ticker
    Given the provider resolves "B020QX2" to ticker "BARC.L" on exchange "LSE"
    When a client requests the ticker for "B020QX2"
    Then the identifier response status is 200
    And the response ticker is "BARC.L"
    And the response identifier_type is "SEDOL"

  Scenario: ISIN resolves correctly with explicit type hint
    Given the provider resolves "US0378331005" to ticker "AAPL" on exchange "NMS"
    When a client requests the ticker for "US0378331005" with type hint "ISIN"
    Then the identifier response status is 200
    And the response ticker is "AAPL"
    And the response identifier_type is "ISIN"
