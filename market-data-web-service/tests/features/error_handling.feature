Feature: Invalid identifier error handling

  Scenario: Unknown ticker returns 404
    Given the API service is running locally
    When a client sends a GET request to /securities/INVALIDXYZ99/price
    Then the response status code is 404
    And the response body contains a field "detail" with a descriptive error message

  Scenario: Malformed ticker special characters returns 422
    Given the API service is running locally
    When a client sends a GET request to /securities/%24/price
    Then the response status code is 422
    And the response body contains a field "detail"

  Scenario: Data source unavailable returns 503
    Given the API service is running locally
    And the upstream data provider is unreachable
    When a client sends a GET request to any valid ticker price endpoint
    Then the response status code is 503
    And the response body contains a field "detail" indicating the upstream dependency is unavailable
