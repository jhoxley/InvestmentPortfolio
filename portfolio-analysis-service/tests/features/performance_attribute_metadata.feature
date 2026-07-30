Feature: Performance Attribute Metadata

  @us4
  Scenario: Performance attribute metadata lists all five measures
    When a request is made to the performance attribute metadata endpoint
    Then the response status is 200
    And the response lists all five supported performance measures: ITD, ITD (Ann.), 1Y, 3Y, and 5Y
    And each listed performance measure includes a human-readable description and a source
    And the performance metadata response body includes a "_links.self" URL
