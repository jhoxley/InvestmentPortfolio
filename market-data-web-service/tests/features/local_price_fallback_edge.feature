Feature: Local price file fallback — edge cases

  Scenario: Missing fallback CSV file returns 503 service error
    Given a fallback configuration maps "PRIV01" to a non-existent CSV file
    When a consumer requests price history for "PRIV01"
    Then the response status is 503
    And the response contains a descriptive error message

  Scenario: Empty fallback CSV file returns 404 not-found error
    Given a fallback configuration maps "PRIV01" to an empty CSV file
    When a consumer requests price history for "PRIV01"
    Then the response status is 404
