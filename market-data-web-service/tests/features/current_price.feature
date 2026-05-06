Feature: Retrieve current security price

  Scenario: Valid ticker returns current price
    Given the API service is running locally
    And the ticker "AAPL" is a valid security listed on a supported exchange
    When a client sends a GET request to /securities/AAPL/price
    Then the response status code is 200
    And the response body contains a numeric field "price"
    And the response body contains a field "currency" with a valid ISO 4217 currency code
    And the response body contains a field "ticker" matching the requested identifier "AAPL"
    And the response body contains a field "timestamp" in ISO 8601 format

  Scenario: Valid London Stock Exchange ticker returns price in GBP
    Given the API service is running locally
    And the ticker "BARC.L" is a valid security on the London Stock Exchange
    When a client sends a GET request to /securities/BARC.L/price
    Then the response status code is 200
    And the field "currency" in the response body is "GBp" or "GBP"

  Scenario: Price field is never zero or negative
    Given the API service is running locally
    When a client requests the price for valid ticker "AAPL"
    Then the returned "price" field is a positive numeric value
