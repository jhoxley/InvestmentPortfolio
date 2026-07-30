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

  @validation
  Scenario: Requesting market_value on an account with only a position ladder succeeds
    Given account "ts-ladder-only-val" has only a position ladder ingested for validation
    When a timeseries request is made for attribute "market_value" for account "ts-ladder-only-val"
    Then the validation response status is 200

  @validation
  Scenario: A start date earlier than the required source's earliest recorded date is rejected
    Given account "ts-early-start-val" has an ingested capital ledger for validation
    When a timeseries request is made for attribute "capital" starting "2000-01-01" for account "ts-early-start-val"
    Then the validation response status is 422
    And the response is a problem detail with type "missing-required-source"

  @validation
  Scenario: Requesting pnl with only the capital ledger ingested is rejected
    Given account "ts-pnl-one-source-val" has an ingested capital ledger for validation
    When a timeseries request is made for attribute "pnl" for account "ts-pnl-one-source-val"
    Then the validation response status is 422
    And the response is a problem detail with type "missing-required-source"

  @validation
  Scenario: An unsupported attribute name is rejected
    Given account "ts-unsupported-attr-val" has an ingested capital ledger for validation
    When a timeseries request is made for attribute "bogus_attribute" for account "ts-unsupported-attr-val"
    Then the validation response status is 422
    And the response is a problem detail with type "unsupported-attribute"

  @validation
  Scenario: A single business day request succeeds with exactly one entry
    Given account "ts-single-day-val" has an ingested capital ledger for validation
    When a timeseries request is made for attribute "capital" with start "2020-01-02" and end "2020-01-02" for account "ts-single-day-val"
    Then the validation response status is 200
    And the timeseries response contains exactly 1 entry

  @validation
  Scenario: Duplicate position query values are treated as a single position
    Given account "pos-duplicate-val" has only a position ladder ingested for validation
    When a position request is made for attribute "market_value" for position "Cash" twice for account "pos-duplicate-val"
    Then the validation response status is 200
    And the position response lists exactly 1 position

  @validation
  Scenario: A valid position with zero overlap with the resolved range produces zero entries, not a failure
    Given account "pos-zero-overlap-val" has a position ladder with "Cash" and a recently-opened "Late Corp" position for validation
    When a position request is made for attribute "market_value" for position "Late Corp" with start "2021-01-04" and end "2021-01-05" for account "pos-zero-overlap-val"
    Then the validation response status is 200
    And the position response contains zero entries

  @validation
  Scenario: Position-name matching is case-sensitive
    Given account "pos-case-val" has only a position ladder ingested for validation
    When a position request is made for attribute "market_value" for position "cash" for account "pos-case-val"
    Then the validation response status is 200
    And the position response contains zero entries

  @validation
  Scenario: A single business day position request succeeds with exactly one entry
    Given account "pos-single-day-val" has a position ladder starting 2020-01-02 for validation
    When a position request is made for attribute "market_value" with start "2020-01-02" and end "2020-01-02" for account "pos-single-day-val"
    Then the validation response status is 200
    And the position response contains exactly 1 entry

  @validation
  Scenario: A divested position still ingests successfully with position_return recorded on its closure date
    Given account "pos-divested-val" has a position ladder where "Sold Corp" is divested to zero quantity for validation
    When a position request is made for attribute "position_return" for position "Sold Corp" for account "pos-divested-val"
    Then the validation response status is 200
    And the position response has no null position_return values

  @validation
  Scenario: Missing mandatory attribute is rejected for the performance endpoint
    Given account "perf-missing-attr-val" has only a position ladder ingested for validation
    When a performance request is made with no attribute for account "perf-missing-attr-val"
    Then the validation response status is 422
    And the response is a problem detail with type "no-attributes-requested"

  @validation
  Scenario: An unsupported attribute name is rejected for the performance endpoint
    Given account "perf-unsupported-attr-val" has only a position ladder ingested for validation
    When a performance request is made for attribute "bogus_measure" for account "perf-unsupported-attr-val"
    Then the validation response status is 422
    And the response is a problem detail with type "unsupported-attribute"

  @validation
  Scenario: Unknown account name is rejected for the performance endpoint
    When a performance request is made for attribute "ITD" for account "perf-unknown-val"
    Then the validation response status is 404
    And the response is a problem detail with type "account-not-found"

  @validation
  Scenario: A known account without a position ladder is rejected for the performance endpoint
    Given account "perf-capital-only-val" has an ingested capital ledger for validation
    When a performance request is made for attribute "ITD" for account "perf-capital-only-val"
    Then the validation response status is 422
    And the response is a problem detail with type "missing-required-source"
