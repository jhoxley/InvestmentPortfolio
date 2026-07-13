Feature: Time Series Attribute Metadata

  @us2
  Scenario: Retrieve the list of supported time series attributes
    When a request is made to the attribute metadata endpoint
    Then the response status is 200
    And the response lists all five supported attributes: capital, income, book_cost, market_value, and pnl
    And each listed attribute includes a human-readable description
    And the response body includes a "_links.self" URL
