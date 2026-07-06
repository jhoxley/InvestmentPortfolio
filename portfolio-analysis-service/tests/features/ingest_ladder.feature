Feature: Position Ladder Ingestion
  As a developer
  I want to submit a sub-account ledger XLSX file
  So that a daily position ladder is generated and stored for later retrieval

  @us1
  Scenario: Successful ingestion of a new sub-account ledger
    Given a valid XLSX file conforming to the sub-account ledger schema
    And the account name "test-portfolio" has no existing position ladder
    When the file is submitted to the ingestion endpoint with account name "test-portfolio"
    Then the response status is 201
    And the response body contains a JSON processing summary with row_count, from_date, to_date, and sub_accounts
    And the response body includes a "_links.download" URL to retrieve the XLSX binary
    And a position ladder XLSX file is persisted to the local store for "test-portfolio"

  @us1
  Scenario: Position forward-fill across days with no activity
    Given a ledger where sub-account "Equity A" has activity on two dates separated by a gap
    And the account name "gap-portfolio" has no existing position ladder
    When the ledger is ingested for account "gap-portfolio"
    Then the ladder contains rows for "Equity A" on every business day in the date range
    And the values for "Equity A" are forward-filled across the gap days

  @us1
  Scenario: Closed equity positions are excluded from subsequent dates
    Given a ledger where sub-account "Equity B" reaches quantity zero on a specific date
    And the account name "closed-portfolio" has no existing position ladder
    When the ledger is ingested for account "closed-portfolio"
    Then the ladder contains rows for "Equity B" up to and including the closure date
    And the ladder contains no rows for "Equity B" on any date after the closure date

  @us1
  Scenario: Cash sub-account always appears regardless of balance
    Given a ledger where the Cash sub-account balance reaches zero on a specific date
    And the account name "cash-portfolio" has no existing position ladder
    When the ledger is ingested for account "cash-portfolio"
    Then the ladder contains a Cash row on every business day in the date range
    And the Cash row on and after the zero-balance date shows a balance of zero

  @us3
  Scenario: Re-submitting the same file is a no-op
    Given a position ladder has already been stored for account "idempotent-portfolio"
    When the same file is submitted again for "idempotent-portfolio"
    Then the response status is 200
    And the response body contains status "unchanged"
    And the stored XLSX file is unchanged
    And the response body includes a "_links.download" URL to the existing stored XLSX

  @us4
  Scenario: Submitting a changed file returns a merge-not-supported error
    Given a position ladder has already been stored for account "conflict-portfolio"
    When a modified file is submitted for "conflict-portfolio"
    Then the response status is 409
    And the response body contains a problem detail with type containing "merge-not-supported"
    And the existing stored ladder for "conflict-portfolio" is unchanged
