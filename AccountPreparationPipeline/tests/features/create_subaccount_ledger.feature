Feature: Create Sub-Account Ledger

  Scenario: Equity positions accumulate book_cost and quantity from single capital ledger
    Given a capital ledger fixture "capital_ledger_a.xlsx"
    When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx"
    Then the exit code is 0
    And the output has a row for "Barclays plc" on "2024-06-01" with book_cost 775.00 and quantity 425.0

  Scenario: Two capital ledgers merge equity sub-accounts by name
    Given a capital ledger fixture "capital_ledger_a.xlsx"
    And a capital ledger fixture "capital_ledger_b.xlsx"
    When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx" "capital_ledger_b.xlsx"
    Then the exit code is 0
    And the output has a row for "Barclays plc" on "2024-06-01" with book_cost 950.00 and quantity 475.0
    And the output has a row for "HSBC Fund" on "2024-02-01" with book_cost 300.00 and quantity 200.0

  Scenario: Dividend income accumulates in total_income from income ledger
    Given a capital ledger fixture "capital_ledger_a.xlsx"
    And an income ledger fixture "income_ledger_a.xlsx"
    When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx" and income ledgers "income_ledger_a.xlsx"
    Then the exit code is 0
    And the output has a row for "Barclays plc" on "2024-07-01" with total_income 55.00
    And the output has a row for "Barclays plc" on "2024-06-01" with book_cost 775.00 and quantity 425.0

  Scenario: Cash rows from income ledger are excluded
    Given a capital ledger fixture "capital_ledger_a.xlsx"
    And an income ledger fixture "income_ledger_a.xlsx"
    When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx" and income ledgers "income_ledger_a.xlsx"
    Then the exit code is 0
    And there is no Cash row with date "2024-04-01" in the output

  Scenario: Cash sub-account has quantity equal to book_cost and zero total_income
    Given a capital ledger fixture "capital_ledger_a.xlsx"
    When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx"
    Then the exit code is 0
    And the Cash row on "2024-01-10" has quantity equal to book_cost
    And the Cash row on "2024-01-10" has total_income 0.00

  Scenario: Mode exits non-zero when a capital ledger file does not exist
    Given a path to a non-existent capital ledger file
    When I run create_subaccount_ledger with that non-existent capital path
    Then the exit code is non-zero
    And the error output mentions the missing file path

  Scenario: Output XLSX has exactly the required columns in order
    Given a capital ledger fixture "capital_ledger_a.xlsx"
    When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx"
    Then the exit code is 0
    And the output XLSX has exactly the columns date, sub_account, book_cost, quantity, total_income in that order
