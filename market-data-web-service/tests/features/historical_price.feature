Feature: Retrieve historical price series

  Scenario: Valid ticker with date range returns daily price series
    Given the API service is running locally
    And the ticker "MSFT" is valid
    When a client sends a GET request to /securities/MSFT/history?from=2024-01-01&to=2024-03-31
    Then the response status code is 200
    And the response body contains a list field "prices"
    And each entry in "prices" contains a "date" in YYYY-MM-DD format and a numeric "close" field
    And the entries are ordered chronologically ascending

  Scenario: Default date range is applied when no dates provided
    Given the API service is running locally
    When a client sends a GET request to /securities/MSFT/history with no date parameters
    Then the response status code is 200
    And the response contains at least one price entry

  Scenario: Start date after end date returns a validation error
    Given the API service is running locally
    When a client sends GET /securities/MSFT/history?from=2024-06-01&to=2024-01-01
    Then the response status code is 422
    And the response body contains a field "detail" describing the validation error
