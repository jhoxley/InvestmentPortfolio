Feature: Create Capital Ledger

  Background:
    Given a simple ledger fixture with deposit, income, buy, and sell rows

  Scenario: Deposit rows accumulate in capital column
    When I run create_capital_ledger
    Then the exit code is 0
    And the capital column carries forward to all dates from the deposit date
    And the income column shows 120.00 from the income date onwards
    And the book_value column is 0.00 before any buy or sell

  Scenario: Buy and sell rows accumulate in book_value column
    When I run create_capital_ledger
    Then the exit code is 0
    And the book_value on 2024-03-20 is -3000.00
    And the book_value on 2024-04-10 is -2200.00

  Scenario: Output has one row per unique date in chronological order
    When I run create_capital_ledger
    Then the exit code is 0
    And the output has 4 rows in ascending date order

  Scenario: Non-qualifying action rows are excluded from all columns
    Given a mixed ledger fixture with additional trading and dividend rows
    When I run create_capital_ledger
    Then the exit code is 0
    And the output row count is 4
    And no column value reflects the excluded transaction amounts

  Scenario: Mode exits with non-zero code when input file does not exist
    Given a path to a non-existent ledger file
    When I run create_capital_ledger
    Then the exit code is non-zero

  Scenario: Pipeline mode accepts input and output path arguments
    Given a valid capital ledger input file
    When I run create_capital_ledger
    Then the exit code is 0
    And the output XLSX is created with the correct columns

  # ─── Lodgement book_value ───────────────────────────────────────────────────

  Scenario: Lodgement rows contribute to book_value column
    Given a ledger fixture with lodgement and buy rows
    When I run create_capital_ledger
    Then the exit code is 0
    And the book_value on "2018-07-12" is 7590.45
    And the book_value on "2019-05-24" is 7790.45
    And the capital column is 0.00 on all rows
    And the income column is 0.00 on all rows
