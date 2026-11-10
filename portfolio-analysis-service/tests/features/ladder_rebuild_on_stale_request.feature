Feature: On-demand ladder rebuild for stale requests

  As a user of the portfolio analysis API, I want a stale account's ladder to be
  rebuilt with real market pricing on demand, rather than silently flat-filled, and I
  want that rebuild to happen at most once and to be correctly superseded by any later
  ledger ingestion that covers the same period.

  @us1
  Scenario: Timeseries request extends past the last ingested date
    Given account "HL-ISA" has a position ladder last known through "2026-09-23"
    And market pricing is available for business days between "2026-09-23" and "2026-11-06"
    When a GET timeseries request is made for market_value from "2026-09-23" to "2026-11-06"
    Then the response contains day-by-day values for "2026-09-24" through "2026-11-06" that vary with market pricing
    And the account's ladder is now known through at least "2026-11-06"

  @us1
  Scenario: Requested end date is in the future
    Given account "HL-ISA" has a position ladder last known through "2026-09-23"
    And today is "2026-11-10"
    When a GET timeseries request is made for market_value from "2026-09-23" to "2026-11-09"
    Then the account's ladder is known through no later than "2026-11-10"

  @us2
  Scenario: Second request after rebuild does not re-trigger sourcing
    Given account "HL-ISA" has a position ladder last known through "2026-09-23"
    And market pricing is available for business days between "2026-09-23" and "2026-11-06"
    When a GET timeseries request is made for market_value from "2026-09-23" to "2026-11-06"
    And the same GET timeseries request is made again
    Then no new market-data calls are made by the second request

  @us3
  Scenario: New ledger supersedes a previously rebuilt period
    Given account "HL-ISA" has a position ladder last known through "2026-09-23"
    And market pricing is available for business days between "2026-09-23" and "2026-11-06"
    And a GET timeseries request is made for market_value from "2026-09-23" to "2026-11-06"
    When a new ledger is ingested containing a trade dated "2026-10-15"
    Then the persisted ladder for "2026-10-15" reflects the newly ingested trade
