Feature: Input Validation
  As a developer
  I want validation errors to be clearly reported
  So that I can identify and fix malformed inputs quickly

  @validation
  Scenario: Invalid account name format is rejected
    When a POST is made with account name "invalid name!"
    Then the validation response status is 422
    And the response is a problem detail with type "invalid-account-name"

  @validation
  Scenario: Account name exceeds 64 characters is rejected
    When a POST is made with account name "a-very-long-account-name-that-exceeds-the-sixty-four-character-limit-yes-it-does"
    Then the validation response status is 422
    And the response is a problem detail with type "invalid-account-name"

  @validation
  Scenario: Non-XLSX upload is rejected
    When a non-XLSX file is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: XLSX missing a required column is rejected
    When an XLSX missing the "quantity" column is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: XLSX with non-numeric value in book_cost is rejected
    When an XLSX with a non-numeric "book_cost" value is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: XLSX with unparseable date is rejected
    When an XLSX with an unparseable date is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: Empty XLSX with no data rows is rejected
    When an XLSX with no data rows is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: Earliest date within 2 business days of today is rejected
    When an XLSX whose earliest date is today is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "empty-date-range"

  @validation
  Scenario: Invalid account name format is rejected for the capital endpoint
    When a capital POST is made with account name "invalid name!"
    Then the validation response status is 422
    And the response is a problem detail with type "invalid-account-name"

  @validation
  Scenario: Non-XLSX upload to the capital endpoint is rejected
    When a non-XLSX file is uploaded for the capital endpoint for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: Capital XLSX missing a required column is rejected
    When a capital XLSX missing the "book_value" column is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: Capital XLSX with non-numeric value in capital is rejected
    When a capital XLSX with a non-numeric "capital" value is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "schema-validation-failed"

  @validation
  Scenario: Capital XLSX with a recorded date range containing no business days is rejected
    When a capital XLSX whose only recorded date is a Saturday is uploaded for account "valid-account"
    Then the validation response status is 422
    And the response is a problem detail with type "empty-capital-date-range"
