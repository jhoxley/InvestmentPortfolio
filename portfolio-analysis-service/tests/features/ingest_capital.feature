Feature: Capital Ledger Ingestion

  @us1
  Scenario: Successful ingestion of a new capital ledger
    Given a valid XLSX file conforming to the capital ledger schema
    And the account name "test-portfolio" has no existing capital ledger
    When the file is submitted to the capital ingestion endpoint with account name "test-portfolio"
    Then the response status is 201
    And the response body contains a JSON processing summary (row count, date range)
    And the response body includes a "_links.download" URL to retrieve the XLSX binary
    And a capital ledger XLSX file is persisted to the local store for "test-portfolio"
    And the ledger contains one row per business day from the earliest to the latest recorded date

  @us1
  Scenario: Capital values forward-fill across days with no recorded observation
    Given a capital ledger with recorded observations on 2024-01-02 and 2024-01-10
    And no observations are recorded on 2024-01-03 through 2024-01-09
    When the ledger is ingested
    Then the ledger contains rows for every business day between 2024-01-02 and 2024-01-10 carrying values forward
    And the row for 2024-01-10 reflects the values recorded on that date

  @us1
  Scenario: Expansion range is bounded by the recorded data, not by today's date
    Given a capital ledger whose latest recorded observation is several months before today
    When the ledger is ingested
    Then the stored capital ledger's last row is the latest business day on or before the latest recorded date
    And no rows are generated for dates after the latest recorded date

  @us3
  Scenario: Re-submitting the same file confirms the ledger is current
    Given a capital ledger has already been stored for account "idempotent-portfolio"
    When the same file is submitted again for "idempotent-portfolio"
    Then the response status is 200
    And the response body contains status "refreshed"
    And the stored ledger's row count and date range are unchanged
    And the response body includes a "_links.download" URL to retrieve the XLSX binary

  @us4
  Scenario: Submitting a changed file returns a merge-not-supported error
    Given a capital ledger has already been stored for account "conflict-portfolio"
    And the stored ledger was generated from file with checksum "abc123"
    When a modified file (checksum "def456") is submitted for "conflict-portfolio"
    Then the response status is 409
    And the response body states that merging an updated capital ledger is not currently supported
    And the existing stored capital ledger for "conflict-portfolio" is unchanged
