Feature: Position Attribute Metadata

  @us3
  Scenario: Retrieve the list of supported position-attribute names
    When a request is made to the position-attribute metadata endpoint
    Then the response status is 200
    And the response lists all six supported attributes: market_value, income, book_cost, pnl, close_price, and quantity
    And "capital" does not appear in the list
    And each listed attribute includes a human-readable description
    And the response body includes a "_links.self" URL
