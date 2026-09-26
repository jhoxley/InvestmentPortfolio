Feature: Account Projection

  @us1
  Scenario: A single requested return produces one historical and one projected series
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with start 2024-01-02, projection_date 2034-01-02, and return "3Y"
    Then the response status is 200
    And the projection response's positions are "Historical" and "3Y"
    And the "Historical" series' final entry date is 2024-01-02
    And the "3Y" series spans 2024-01-02 through 2034-01-02

  @us1
  Scenario: The projected series begins at the historical series' final recorded value
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with start 2024-01-02, projection_date 2034-01-02, and return "3Y"
    Then the response status is 200
    And the "3Y" series' first entry's market_value equals the "Historical" series' final entry's market_value

  @us1
  Scenario: The projected series compounds the requested return's own historical rate
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with start 2024-01-02, projection_date 2024-01-16, and return "3Y"
    Then the response status is 200
    And every "3Y" entry's market_value matches the compounding formula using the account's own 3Y return on 2024-01-02

  @us1
  Scenario: A projection_date not later than the resolved start is rejected
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with start 2024-01-02, projection_date 2024-01-02, and no return
    Then the response status is 422
    And the problem detail type ends with "invalid-projection-range"

  @us2
  Scenario: Multiple requested returns each produce their own series from a shared starting point
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with start 2024-01-02, projection_date 2034-01-02, and returns "1Y" and "3Y"
    Then the response status is 200
    And the projection response's positions are "1Y", "3Y", and "Historical"
    And the "1Y" and "3Y" series' first entries share the same market_value

  @us2
  Scenario: A requested return without enough recorded history is silently omitted
    Given account "young-portfolio" has an ingested position ladder starting 6 months ago
    When a projection request is made with no start, a projection_date 10 years from today, and returns "5Y" and "1Y"
    Then the response status is 200
    And the projection response's positions do not include "5Y"

  @us2
  Scenario: Requesting no returns at all still returns the historical series
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with start 2024-01-02, projection_date 2034-01-02, and no return
    Then the response status is 200
    And the projection response's positions are "Historical"

  @us3
  Scenario: Omitting start defaults to the account's most recently recorded date
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a projection request is made with no start, a projection_date 10 years from today, and return "1Y"
    Then the response status is 200
    And the "Historical" series' final entry date equals the account's own most recently recorded date

  @us3
  Scenario: An account with a capital ledger but no position ladder is rejected
    Given account "capital-only-portfolio" has an ingested capital ledger but no position ladder
    When a projection request is made with no start, a projection_date 10 years from today, and no return
    Then the response status is 422
    And the problem detail type ends with "position-ladder-not-ingested"

  @us3
  Scenario: An account with no ingested resource at all is rejected
    Given no resource of any kind has been ingested for account "nowhere-portfolio"
    When a projection request is made with no start, a projection_date 10 years from today, and no return
    Then the response status is 404
    And the problem detail type ends with "account-not-found"

  @us1
  Scenario: Monthly projection with a mid-month start omits the start-date entry
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "month" projection request is made with start 2024-01-17, projection_date 2024-04-20, and return "3Y"
    Then the response status is 200
    And the "Historical" series' final entry date is 2024-01-01
    And the "3Y" series has no entry dated 2024-01-17
    And the "3Y" series' first entry date is 2024-02-01

  @us1
  Scenario: Monthly projection ends at the last month start on or before projection_date
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "month" projection request is made with start 2024-01-17, projection_date 2024-04-20, and return "3Y"
    Then the response status is 200
    And the "3Y" series has no entry dated 2024-04-20
    And the "3Y" series' final entry date is 2024-04-01

  @us1
  Scenario: Quarterly projection begins at the next quarter start
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "quarter" projection request is made with start 2024-02-14, projection_date 2024-10-20, and return "3Y"
    Then the response status is 200
    And the "3Y" series has no entry dated 2024-02-14
    And the "3Y" series' first entry date is 2024-04-01
    And the "3Y" series' final entry date is 2024-10-01

  @us1
  Scenario: Weekly projection begins at the next Monday
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "week" projection request is made with start 2024-01-17, projection_date 2024-02-01, and return "3Y"
    Then the response status is 200
    And the "3Y" series has no entry dated 2024-01-17
    And the "3Y" series' first entry date is 2024-01-22
    And the "3Y" series' final entry date is 2024-01-29

  @us2
  Scenario: Monthly projection with a start on a month start retains the start-date entry
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "month" projection request is made with start 2024-02-01, projection_date 2024-04-20, and return "3Y"
    Then the response status is 200
    And the "3Y" series' first entry date is 2024-02-01

  @us2
  Scenario: Monthly projection whose month began on a weekend retains a first-business-day start
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "month" projection request is made with start 2024-09-02, projection_date 2024-12-20, and return "3Y"
    Then the response status is 200
    And the "3Y" series' first entry date is 2024-09-02

  @us2
  Scenario: Daily projection retains the start-date entry
    Given account "proj-portfolio" has an ingested position ladder spanning 2016-01-02 through today
    When a "day" projection request is made with start 2024-01-17, projection_date 2024-01-31, and return "3Y"
    Then the response status is 200
    And the "3Y" series' first entry date is 2024-01-17
