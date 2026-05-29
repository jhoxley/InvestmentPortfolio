Feature: Identifier-to-Ticker Lookup — Error Handling

  Scenario: Identifier with invalid format is rejected
    When a client requests the ticker for identifier "NOT-VALID-FORMAT"
    Then the identifier response status is 422
    And the response contains an identifier format error

  Scenario: Valid-format identifier that cannot be resolved returns not-found
    Given the provider cannot resolve "US0000000000"
    When a client requests the ticker for identifier "US0000000000"
    Then the identifier response status is 404
    And the response contains an identifier not found error

  Scenario: Type hint provided but format conflicts
    When a client requests the ticker for "NOT-VALID" with type hint "ISIN"
    Then the identifier response status is 422
    And the response contains an identifier format error

  Scenario: Provider unavailable returns 503
    Given the identifier provider is unavailable
    When a client requests the ticker for identifier "US0378331005"
    Then the identifier response status is 503
