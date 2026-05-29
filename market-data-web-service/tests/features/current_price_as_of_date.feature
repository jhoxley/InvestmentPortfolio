Feature: As-of date on current price response

  Scenario: Current price response includes an as-of date
    Given the API service is running locally
    And the ticker "AAPL" is a valid security listed on a supported exchange
    When a client sends a GET request to /securities/AAPL/price
    Then the response status code is 200
    And the response body contains a field "as_of_date" in YYYY-MM-DD format

  Scenario: As-of date is a valid past or current trading date
    Given the API service is running locally
    When a client sends a GET request to /securities/AAPL/price
    Then the response status code is 200
    And the "as_of_date" field is not a future date
    And the "as_of_date" field is not a Saturday or Sunday

  Scenario: As-of date reconciles with the history endpoint
    Given the API service is running locally
    And the ticker "MSFT" is a valid security
    When a client sends a GET request to /securities/MSFT/price
    And a client also sends a GET request to /securities/MSFT/history with no date parameters
    Then the "as_of_date" in the price response matches the "date" of the last entry in the history "prices" list
