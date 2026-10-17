Feature: Time Series Periodicity

  Optional calendar-aligned aggregation of the account and position time series endpoints.

  @us1
  Scenario: Annual periodicity collapses a multi-year daily series into one entry per calendar year
    Given account "decade-portfolio" has a capital ledger recorded from 2016-01-04 to 2025-12-31
    When a request is made for attribute "capital" from 2016-01-04 to 2025-12-31 with periodicity "annual"
    Then the response status is 200
    And the response contains exactly 10 entries
    And every entry date is the first business day on or after 01 January of its calendar year
    And each entry value for "capital" equals the daily series value on the last business day of its window

  @us1
  Scenario: Monthly periodicity divides the same range into calendar months
    Given account "decade-portfolio" has a capital ledger recorded from 2016-01-04 to 2025-12-31
    When a request is made for attribute "capital" from 2016-01-04 to 2025-12-31 with periodicity "month"
    Then the response status is 200
    And the response contains exactly 120 entries
    And every entry date is the first business day on or after the 1st of its calendar month

  @us1
  Scenario: Weekly periodicity aligns to calendar weeks beginning on Monday
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" from 2026-01-05 to 2026-02-27 with periodicity "week"
    Then the response status is 200
    And every entry date falls on a Monday or the first business day of its calendar week
    And each entry value for "capital" equals the daily series value on the last business day of its window

  @us1
  Scenario: Aggregated entries carry the last observation of every requested attribute
    Given account "dual-portfolio" has a capital ledger and position ladder recorded from 2026-01-05 to 2026-02-27
    When a request is made for attributes "capital" and "market_value" from 2026-01-05 to 2026-02-27 with periodicity "month"
    Then the response status is 200
    And the response contains exactly 2 entries
    And every entry contains a "capital" value and a "market_value" value
    And all values on each entry come from the same source date in the daily series

  @us1
  Scenario: Omitting periodicity preserves today's per-business-day behaviour
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" from 2026-01-05 to 2026-02-27 with no periodicity parameter
    Then the response status is 200
    And the response contains one entry per business day in the range
    And the response body is identical to the same request with periodicity "day" apart from the periodicity field

  @us2
  Scenario: Quarterly periodicity aggregates each position independently
    Given account "multi-position" has a position ladder holding positions "Cash" and "Equity A" recorded from 2025-01-01 to 2025-12-31
    When a position request is made for attribute "market_value" from 2025-01-01 to 2025-12-31 with periodicity "quarter"
    Then the response status is 200
    And the response contains exactly 8 entries
    And every entry date is the first business day on or after the 1st of January, April, July or October
    And every position sharing a window carries the same entry date
    And each entry value for "market_value" equals that position's daily value on the last business day of its window

  @us2
  Scenario: A position with data in only part of the range appears only in the periods it covers
    Given account "partial-position" has a position ladder where position "Equity A" holds data only from 2025-04-01 to 2025-06-30
    When a position request is made for position "Equity A" and attribute "market_value" from 2025-01-01 to 2025-12-31 with periodicity "quarter"
    Then the response status is 200
    And the response contains exactly 1 entry
    And every entry date is exactly 2025-04-01

  @us2
  Scenario: Omitting periodicity preserves today's per-business-day position behaviour
    Given account "single-position" has a position ladder holding positions "Cash" and "Equity A" recorded from 2026-01-05 to 2026-02-27
    When a position request is made for attribute "market_value" from 2026-01-05 to 2026-02-27 with no periodicity parameter
    Then the response status is 200
    And the response contains one entry per business day and position in the range
    And the response body is identical to the same request with periodicity "day" apart from the periodicity field

  @us3 @validation
  Scenario: An unsupported periodicity value is rejected with a validation error
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" with periodicity "fortnight"
    Then the response status is 422
    And the error is an RFC 7807 problem document of type "unsupported-periodicity"
    And the error names every supported periodicity value

  @us3 @validation
  Scenario: The position endpoint rejects an unsupported periodicity identically
    Given account "single-position" has a position ladder holding positions "Cash" and "Equity A" recorded from 2026-01-05 to 2026-02-27
    When a position request is made for attribute "market_value" with periodicity "fortnight"
    Then the response status is 422
    And the error is an RFC 7807 problem document of type "unsupported-periodicity"
    And the error names every supported periodicity value

  @us3 @validation
  Scenario: A synonym or differently-cased value is rejected too
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" with periodicity "Annual"
    Then the response status is 422
    And the error is an RFC 7807 problem document of type "unsupported-periodicity"

  @us3
  Scenario: The applied periodicity is reported in the response
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" from 2026-01-05 to 2026-02-27 with periodicity "month"
    Then the response status is 200
    And the response reports its periodicity as "month"

  @us3
  Scenario: The default periodicity is reported when none was requested
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" from 2026-01-05 to 2026-02-27 with no periodicity parameter
    Then the response status is 200
    And the response reports its periodicity as "day"

  @us3
  Scenario: Explicitly requesting day periodicity behaves as the default
    Given account "short-portfolio" has a capital ledger recorded from 2026-01-05 to 2026-02-27
    When a request is made for attribute "capital" from 2026-01-05 to 2026-02-27 with periodicity "day"
    Then the response status is 200
    And the response is identical to the same request made with no periodicity parameter
