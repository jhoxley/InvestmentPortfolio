Feature: Journal Fragment Consolidation
  As a user with financial transaction exports from Hargreaves Lansdown
  I want to consolidate journal fragment files into a standardised XLSX journal
  So that I have a single, normalised record of all my investment transactions

  # ─── User Story 1: First-Time Consolidation ────────────────────────────────

  Scenario: Creates a new journal from valid HL CSV exports
    Given a directory of valid HL CSV files
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the consolidated journal XLSX is created
    And the journal contains the correct columns
    And the journal contains 6 events

  Scenario: Skips preamble rows before HL CSV header
    Given an HL CSV file with metadata preamble rows before the header
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 6 events

  Scenario: Maps B-reference to buy action
    Given a valid HL CSV file with a buy transaction reference
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains a row with action "buy"

  Scenario: Maps S-reference to sell action
    Given a valid HL CSV file with a sell transaction reference
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains a row with action "sell"

  Scenario: Maps Deposit and BACS references to deposit action
    Given a valid HL CSV file with Deposit and BACS rows
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 2 rows with action "deposit"

  Scenario: Strips unit cost and quantity suffix from description
    Given a valid HL CSV file with a buy transaction reference
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the journal sub_account does not contain "@"

  # ─── User Story 2: Incremental Update ─────────────────────────────────────

  Scenario: Re-running with same inputs inserts zero events
    Given a directory of valid HL CSV files
    And no existing consolidated journal
    And I have already run consolidate_journals once
    When I run consolidate_journals again with the same inputs
    Then the exit code is 0
    And the stdout summary shows 0 events inserted

  Scenario: Incremental run adds only new events
    Given an existing consolidated journal with 3 events
    And a directory containing a new HL CSV file with 2 different events
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the stdout summary shows 2 events inserted
    And the journal contains 8 events total

  # ─── User Story 3: Graceful Error Handling ─────────────────────────────────

  Scenario: Valid file processes despite co-located invalid file
    Given a directory containing one valid and one invalid HL CSV file
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains events from the valid file only
    And the stdout summary contains an ERRORS section

  Scenario: No-header file is reported in errors section
    Given a directory containing only an HL CSV file with no recognisable header
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the stdout summary contains an ERRORS section
    And the stdout summary mentions the invalid file name

  Scenario: Bad-value row reported with line number, surrounding rows still processed
    Given a directory containing an HL CSV file with one bad-value row
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 2 events total
    And the stdout summary contains an ERRORS section

  # ─── Trade Cash Offset Entries ──────────────────────────────────────────────

  Scenario: Offset rows are generated for buy and sell trades
    Given a directory of valid HL CSV files
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 3 rows with action "trading"

  Scenario: No offset rows generated for deposit-only input
    Given a valid HL CSV file with Deposit and BACS rows
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 0 rows with action "trading"

  Scenario: Existing journal receives backfilled offsets on first post-deployment run
    Given a journal already containing a buy trade but no offset row
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 1 rows with action "trading"

  Scenario: Re-running with same inputs does not duplicate offset rows
    Given a directory of valid HL CSV files
    And no existing consolidated journal
    And I have already run consolidate_journals once
    When I run consolidate_journals again with the same inputs
    Then the exit code is 0
    And the journal contains 3 rows with action "trading"

  Scenario: Incremental run adds offsets only for new trades
    Given an existing consolidated journal with 3 events
    And a directory containing a new HL CSV file with 2 different events
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 3 rows with action "trading"

  Scenario: Events inserted count includes offset rows
    Given a directory of valid HL CSV files
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the stdout summary shows 6 events inserted

  # ─── User Story 3: Stale Offset Correction ──────────────────────────────────

  Scenario: Re-running corrects a wrong-sign buy offset from a previous run
    Given a journal with a wrong-sign buy offset row
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the buy offset row has a negative value
