---

description: "Task list for Feature 014: Sub-Account Consolidated Ledger"
---

# Tasks: Sub-Account Consolidated Ledger

**Input**: Design documents from `specs/014-subaccount-ledger/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Tests are MANDATORY per the project constitution. TDD sequence is strictly:
write tests → confirm they FAIL → implement → confirm they PASS.

**Organization**: Three user stories (P1 → P2 → P3). Tasks grouped into:
Setup → Foundational → US1 (equity positions) → US2 (dividend income) → US3 (Cash balance) → Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US1/US2/US3]**: Belongs to the labelled user story

---

## Phase 1: Setup

**Purpose**: Create directory structure and package marker files before any code is written.

- [X] T001 Create `src/modes/create_subaccount_ledger/__init__.py` as an empty file
- [X] T002 [P] Create `tests/unit/create_subaccount_ledger/__init__.py` as an empty file
- [X] T003 [P] Create `tests/data/create_subaccount_ledger/` directory (empty; populated by T005–T006)

**Checkpoint**: Directory skeleton ready — constants, fixtures, and tests can now be added.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared constants and XLSX test fixtures required by every user story phase.

- [X] T004 Create `src/modes/create_subaccount_ledger/constants.py` with the following (no magic strings anywhere else):
  ```python
  # Input columns
  LEDGER_COL_DATE = "date"
  LEDGER_COL_SUB_ACCOUNT = "sub_account"
  LEDGER_COL_ACTION = "action"
  LEDGER_COL_TV = "Transaction Value"
  LEDGER_COL_TQ = "Transaction Quantity"

  # Action strings
  ACTION_BUY = "buy"
  ACTION_SELL = "sell"
  ACTION_LODGEMENT = "lodgement"
  ACTION_DIVIDEND = "dividend"

  EQUITY_ACTIONS: frozenset[str] = frozenset({"buy", "sell", "lodgement"})
  CASH_SUB_ACCOUNT: str = "Cash"

  # Output columns
  OUT_COL_DATE = "date"
  OUT_COL_SUB_ACCOUNT = "sub_account"
  OUT_COL_BOOK_COST = "book_cost"
  OUT_COL_QUANTITY = "quantity"
  OUT_COL_TOTAL_INCOME = "total_income"
  OUTPUT_COLUMNS: list[str] = ["date", "sub_account", "book_cost", "quantity", "total_income"]

  # Logging
  LOG_CORRELATION_ID = "correlation_id"
  COMPLETION_MSG = "Sub-account ledger written"
  ```

- [X] T005 Create `tests/data/create_subaccount_ledger/create_fixtures.py`. Columns for all DataFrames: `["Transaction ID", "date", "account", "sub_account", "action", "reference", "Account Value", "Account Quantity", "Transaction Value", "Transaction Quantity"]`. Generate three fixtures:

  **`capital_ledger_a.xlsx`** (7 rows — SIPP-like capital ledger):
  | Transaction ID | date | account | sub_account | action | reference | Account Value | Account Quantity | Transaction Value | Transaction Quantity |
  |---|---|---|---|---|---|---|---|---|---|
  | 00001-001 | 2024-01-10 | HL SIPP | Cash | deposit | REF001 | 5000.00 | 0 | 5000.00 | 0 |
  | 00002-001 | 2024-01-10 | HL SIPP | Barclays plc | buy | REF002 | 200.00 | 100 | 200.00 | 100 |
  | 00002-002 | 2024-01-10 | HL SIPP | Cash | trading | REF002-offset | 4800.00 | 0 | -200.00 | 0 |
  | 00003-001 | 2024-01-10 | HL SIPP | Barclays plc | lodgement | REF003 | 700.00 | 400 | -500.00 | 300 |
  | 00004-001 | 2024-03-15 | HL SIPP | Barclays plc | buy | REF004 | 850.00 | 450 | 150.00 | 50 |
  | 00004-002 | 2024-03-15 | HL SIPP | Cash | trading | REF004-offset | 4650.00 | 0 | -150.00 | 0 |
  | 00005-001 | 2024-06-01 | HL SIPP | Barclays plc | sell | REF005 | 775.00 | 425 | -75.00 | -25 |

  Expected "Barclays plc" cumulative output from capital_ledger_a only:
  - 2024-01-10: `book_cost=700.00` (buy +200 + lodgement −(−500)), `quantity=400`
  - 2024-03-15: `book_cost=850.00`, `quantity=450`
  - 2024-06-01: `book_cost=775.00`, `quantity=425`

  Expected Cash cumulative output:
  - 2024-01-10: `book_cost=quantity=4800.00` (deposit 5000 + trading −200)
  - 2024-03-15: `book_cost=quantity=4650.00`

  **`capital_ledger_b.xlsx`** (3 rows — second capital ledger with overlapping and distinct sub-accounts):
  | Transaction ID | date | account | sub_account | action | reference | Account Value | Account Quantity | Transaction Value | Transaction Quantity |
  |---|---|---|---|---|---|---|---|---|---|
  | 00010-001 | 2024-02-01 | HL ISA | Barclays plc | buy | REF010 | 175.00 | 50 | 175.00 | 50 |
  | 00011-001 | 2024-02-01 | HL ISA | HSBC Fund | buy | REF011 | 300.00 | 200 | 300.00 | 200 |
  | 00011-002 | 2024-02-01 | HL ISA | Cash | deposit | REF011-dep | 2000.00 | 0 | 2000.00 | 0 |

  Expected merged "Barclays plc" when both capital ledgers combined:
  - 2024-01-10: `book_cost=700.00`, `quantity=400` (capital_a only)
  - 2024-02-01: `book_cost=875.00`, `quantity=450` (adds capital_b buy: +175 / +50)
  - 2024-03-15: `book_cost=1025.00`, `quantity=500` (adds capital_a buy: +150 / +50)
  - 2024-06-01: `book_cost=950.00`, `quantity=475` (adds capital_a sell: −75 / −25)

  **`income_ledger_a.xlsx`** (4 rows — income ledger with dividends and Cash rows):
  | Transaction ID | date | account | sub_account | action | reference | Account Value | Account Quantity | Transaction Value | Transaction Quantity |
  |---|---|---|---|---|---|---|---|---|---|
  | 00020-001 | 2024-04-01 | HL SIPP Income | Barclays plc | dividend | DIV001 | 25.00 | 425 | 25.00 | 425 |
  | 00020-002 | 2024-04-01 | HL SIPP Income | Cash | income | DIV001-cash | 25.00 | 0 | 25.00 | 0 |
  | 00021-001 | 2024-07-01 | HL SIPP Income | Barclays plc | dividend | DIV002 | 55.00 | 425 | 30.00 | 425 |
  | 00021-002 | 2024-07-01 | HL SIPP Income | Cash | income | DIV002-cash | 55.00 | 0 | 30.00 | 0 |

  Expected "Barclays plc" total_income cumulative: 2024-04-01 → 25.00; 2024-07-01 → 55.00.
  Cash rows from this file MUST be excluded from output (FR-007).

  Write the file using `df.to_excel(path, index=False, engine="openpyxl")`. Add a `main()` guard and call it from `if __name__ == "__main__"`.

- [X] T006 Run `python tests/data/create_subaccount_ledger/create_fixtures.py` to generate `capital_ledger_a.xlsx`, `capital_ledger_b.xlsx`, and `income_ledger_a.xlsx` in `tests/data/create_subaccount_ledger/`

**Checkpoint**: Constants and XLSX fixtures available — story-level work can now begin.

---

## Phase 3: User Story 1 — Consolidated Equity Positions (Priority: P1) 🎯 MVP

**Goal**: Given one or more capital ledger XLSX files, produce a single output where each (date, sub-account) equity pair has the correct cumulative `book_cost` and `quantity` from buy, sell, and lodgement events across all capital inputs.

**Independent Test**: Run against `capital_ledger_a.xlsx` only; verify "Barclays plc" at 2024-06-01 has `book_cost=775.00` and `quantity=425`. Run against both capital fixtures; verify merged "Barclays plc" at 2024-06-01 has `book_cost=950.00` and `quantity=475`.

### Tests for User Story 1 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T011)

- [X] T007 [P] [US1] Write `TestEquityPositions` class in `tests/unit/create_subaccount_ledger/test_engine.py`. Add a helper `_df(*rows)` that builds a DataFrame from tuples and a helper `_row(date, sub_account, action, tv, tq)` that returns a dict with all required ledger columns. Write 8 tests (all call `SubAccountLedgerEngine().run(capital_dfs=[df], income_dfs=[])`):
  - `test_single_buy_produces_book_cost_and_quantity` — one buy row (TV=200, TQ=100); result has one row with `book_cost=200.0` and `quantity=100.0`
  - `test_sell_reduces_book_cost_and_quantity` — buy (TV=200, TQ=100) then sell (TV=−75, TQ=−25); row at sell date has `book_cost=125.0`, `quantity=75.0`
  - `test_lodgement_adds_positive_book_cost` — lodgement (TV=−500, TQ=300); `book_cost=500.0` (negated)
  - `test_lodgement_adds_positive_quantity` — same lodgement; `quantity=300.0`
  - `test_two_buys_same_date_same_subaccount_summed` — two buy rows same date same sub_account (TV=200 each); single output row with `book_cost=400.0`
  - `test_buys_across_two_capital_dfs_merged` — buy in capital_df_1, buy in capital_df_2 for same sub_account; `run(capital_dfs=[df1, df2], income_dfs=[])` → single cumulative position
  - `test_equity_from_income_df_included` — equity buy row passed in `income_dfs` (sub_account != "Cash"); contributes to `book_cost` (buy/sell/lodgement are listed action types in FR-009 and are included regardless of which input list the row came from; the FR-009 exception clause applies only to the Cash sub-account, not to equity rows from income files)
  - `test_equity_actions_only_no_dividend_in_book_cost` — buy + dividend rows for same sub_account; dividend does NOT appear in `book_cost` or `quantity` columns

- [X] T008 [P] [US1] Write `tests/features/create_subaccount_ledger.feature` with 2 US1 scenarios:
  ```gherkin
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
  ```

- [X] T009 [P] [US1] Create `tests/features/steps/create_subaccount_ledger_steps.py`. Add:
  - `@scenario` bindings: `test_equity_accumulate_single_capital`, `test_two_capital_ledgers_merge`
  - `@given(parsers.parse('a capital ledger fixture "{filename}"'))` — copies `tests/data/create_subaccount_ledger/{filename}` to tmp_path; stores path in `state["capital_paths"]` list
  - `@when(parsers.parse('I run create_subaccount_ledger with capital ledgers {filenames}'))` — builds `python pipeline.py create_subaccount_ledger {output_path} --capital {paths}` command; runs via subprocess; stores `returncode` and `output_path` in `state`
  - `@then(parsers.parse('the exit code is {code:d}'))` — asserts `state["returncode"] == code`
  - `@then(parsers.parse('the output has a row for "{sub_account}" on "{date}" with book_cost {book_cost:f} and quantity {quantity:f}'))` — reads output XLSX, locates row, asserts both values with `pytest.approx`

- [X] T010 [US1] Confirm all 8 `TestEquityPositions` unit tests FAIL (RED): run `python -m pytest tests/unit/create_subaccount_ledger/test_engine.py -v` — all must fail with `ImportError` or `AttributeError` (engine not yet implemented)

### Implementation for User Story 1

- [X] T011 [US1] Create `src/modes/create_subaccount_ledger/engine.py`. Implement `SubAccountLedgerEngine` with a `run(self, capital_dfs: list[pd.DataFrame], income_dfs: list[pd.DataFrame]) -> pd.DataFrame` method. **Pass 1 only** (Passes 2 and 3 come in later stories):
  1. Concatenate all capital + income DataFrames into one pool (`pd.concat(..., ignore_index=True)`)
  2. Filter to equity actions: `action.isin(EQUITY_ACTIONS)` AND `sub_account != CASH_SUB_ACCOUNT`
  3. Compute `_bv_contrib`: `TV` for buy/sell; `−TV` for lodgement (lodgement TV is negative, negation makes it positive)
  4. Compute `_qty_contrib`: `TQ` for all equity actions
  5. Group by `(date, sub_account)`, sum `_bv_contrib` and `_qty_contrib` — one row per (date, sub_account) after grouping
  6. Sort by `date` within each `sub_account` group; cumsum `_bv_contrib` → `book_cost`, cumsum `_qty_contrib` → `quantity`
  7. Add `total_income=0.0` column (Pass 2 will replace this)
  8. Return `result[OUTPUT_COLUMNS]` sorted by `(date, sub_account)`; return empty DataFrame with `OUTPUT_COLUMNS` if no equity rows exist

- [X] T012 [US1] Create `src/modes/create_subaccount_ledger/mode.py`. Implement `CreateSubAccountLedgerMode`:
  - `name = "create_subaccount_ledger"`
  - `register_arguments(parser)`: positional `output_path`; `--capital LEDGER [LEDGER...]` (nargs='+', required=True); `--income LEDGER [LEDGER...]` (nargs='*', default=[])
  - `execute(context, args) -> int`:
    1. Log correlation_id (use `uuid.uuid4()` truncated to 8 chars) and input file counts
    2. Validate all --capital paths exist; exit 1 with descriptive error if any missing
    3. Load capital DataFrames: `[pd.read_excel(p, engine="openpyxl") for p in args.capital]`
    4. Load income DataFrames: `[pd.read_excel(p, engine="openpyxl") for p in args.income]` (may be empty)
    5. Call `SubAccountLedgerEngine().run(capital_dfs, income_dfs)`
    6. Write result to `args.output_path` using `pd.ExcelWriter` + openpyxl engine
    7. Log rows_written and COMPLETION_MSG
    8. Return 0

- [X] T013 [US1] Register `CreateSubAccountLedgerMode` in `pipeline.py`: add `from src.modes.create_subaccount_ledger.mode import CreateSubAccountLedgerMode` import and `registry.register(CreateSubAccountLedgerMode())` in `_build_registry()`

- [X] T014 [US1] Confirm US1 tests pass (GREEN): run `python -m pytest tests/unit/create_subaccount_ledger/test_engine.py::TestEquityPositions tests/features/steps/create_subaccount_ledger_steps.py -k "equity_accumulate or two_capital" -v` — all 8 unit tests and 2 BDD scenarios must pass; existing tests must not regress

**Checkpoint**: US1 complete. Single and multi-ledger equity accumulation is functional and tested.

---

## Phase 4: User Story 2 — Accumulated Dividend Income Per Holding (Priority: P2)

**Goal**: Dividend Transaction Values from all input ledgers (capital or income) accumulate into `total_income` per sub-account. The dividend Transaction Quantity is ignored.

**Independent Test**: Run against `capital_ledger_a.xlsx` + `income_ledger_a.xlsx`; verify "Barclays plc" at 2024-07-01 has `total_income=55.00` (cumulative of 25.00 + 30.00 dividends). Verify `book_cost` and `quantity` are unchanged from Phase 3 values.

### Tests for User Story 2 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T019)

- [X] T015 [P] [US2] Add `TestDividendIncome` class to `tests/unit/create_subaccount_ledger/test_engine.py` with 4 tests (all call `run(capital_dfs=[df], income_dfs=[])`):
  - `test_dividend_contributes_to_total_income` — one dividend row (TV=25, TQ=425); result row has `total_income=25.0`
  - `test_dividend_tv_used_not_tq` — dividend with TV=25.00 and TQ=999; `total_income=25.0`, NOT 999
  - `test_dividend_on_date_with_no_buy_keeps_book_cost_zero` — dividend-only sub-account (no buy/sell/lodgement); output row has `book_cost=0.0`, `quantity=0.0`, `total_income=25.0`
  - `test_two_dividends_cumulative` — two dividend rows on different dates (TV=25, TV=30); first date `total_income=25.0`, second date `total_income=55.0`

- [X] T016 [P] [US2] Add 1 US2 BDD scenario to `tests/features/create_subaccount_ledger.feature`:
  ```gherkin
    Scenario: Dividend income accumulates in total_income from income ledger
      Given a capital ledger fixture "capital_ledger_a.xlsx"
      And an income ledger fixture "income_ledger_a.xlsx"
      When I run create_subaccount_ledger with capital ledgers "capital_ledger_a.xlsx" and income ledgers "income_ledger_a.xlsx"
      Then the exit code is 0
      And the output has a row for "Barclays plc" on "2024-07-01" with total_income 55.00
      And the output has a row for "Barclays plc" on "2024-06-01" with book_cost 775.00 and quantity 425.0
  ```

- [X] T017 [P] [US2] Add to `tests/features/steps/create_subaccount_ledger_steps.py`:
  - `@scenario` binding: `test_dividend_income_accumulates`
  - `@given(parsers.parse('an income ledger fixture "{filename}"'))` — copies `tests/data/create_subaccount_ledger/{filename}` to tmp_path; stores in `state["income_paths"]`
  - `@when(parsers.parse('I run create_subaccount_ledger with capital ledgers {cap_files} and income ledgers {inc_files}'))` — builds command with both `--capital` and `--income` flags; runs subprocess
  - `@then(parsers.parse('the output has a row for "{sub_account}" on "{date}" with total_income {expected:f}'))` — reads output XLSX, locates row, asserts `total_income` with `pytest.approx`

- [X] T018 [US2] Confirm `TestDividendIncome` tests FAIL (RED): run `python -m pytest tests/unit/create_subaccount_ledger/test_engine.py::TestDividendIncome -v` — all 4 must fail (total_income is currently always 0)

### Implementation for User Story 2

- [X] T019 [US2] Add **Pass 2** to `SubAccountLedgerEngine.run()` in `src/modes/create_subaccount_ledger/engine.py`:
  1. From the same pooled DataFrame (capital + all income rows — at this phase, mode.py has not yet stripped income Cash rows; this is safe because Passes 1 and 2 both filter `sub_account != CASH_SUB_ACCOUNT`, so income Cash rows are excluded by the engine's own filters even before T026 is implemented), filter `action == ACTION_DIVIDEND` AND `sub_account != CASH_SUB_ACCOUNT`
  2. Compute `_income_contrib = TV`
  3. Group by `(date, sub_account)`, sum `_income_contrib`
  4. Sort by `date` within each `sub_account`, cumsum `_income_contrib` → `total_income`
  5. Outer-join equity result (Pass 1) with income result (Pass 2) on `(date, sub_account)`, fill NaN with 0.0
  6. Return merged result with `OUTPUT_COLUMNS` sorted by `(date, sub_account)`; handle empty Pass 2 gracefully

- [X] T020 [US2] Confirm US2 tests pass (GREEN): run `python -m pytest tests/unit/create_subaccount_ledger/test_engine.py::TestDividendIncome tests/features/steps/create_subaccount_ledger_steps.py -k "dividend_income" -v` — all 4 unit tests and 1 BDD scenario must pass

**Checkpoint**: US2 complete. Equity positions and dividend income are both functional and tested.

---

## Phase 5: User Story 3 — Cash Balance Without Double-Counting (Priority: P3)

**Goal**: Cash sub-account rows from capital ledgers produce output rows where `quantity == book_cost == cumulative cash balance` and `total_income == 0`. Cash sub-account rows from income-designated ledgers are excluded entirely (FR-007). Mode validates input file existence and exits non-zero on error.

**Independent Test**: Run against `capital_ledger_a.xlsx` (--capital) + `income_ledger_a.xlsx` (--income); verify Cash output rows have no source from income ledger (only 2024-01-10 and 2024-03-15 Cash rows from capital_ledger_a appear); verify `quantity == book_cost` and `total_income == 0` for each Cash row.

### Tests for User Story 3 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T025)

- [X] T021 [P] [US3] Add `TestCashHandling` (5 tests) and `TestOutputSchema` (4 tests) to `tests/unit/create_subaccount_ledger/test_engine.py`:

  **TestCashHandling**:
  - `test_cash_from_capital_df_present` — Capital df with Cash deposit row; Cash sub_account appears in result
  - `test_cash_from_income_df_excluded` — construct an income_df containing one Cash row (action="income", sub_account="Cash", TV=+50.00); call `run(capital_dfs=[], income_dfs=[income_df])`; assert no "Cash" row appears in the result. This tests that Pass 3 ignores income_dfs entirely (Pass 3 only reads capital_dfs) and that Passes 1 and 2 filter out Cash rows, so income Cash rows never produce output regardless of T026
  - `test_cash_quantity_equals_book_cost` — Capital df with Cash deposit (TV=5000) and trading (TV=−200); Cash row has `quantity == book_cost == 4800.0`
  - `test_cash_total_income_is_zero` — Same setup; Cash row has `total_income == 0.0`
  - `test_cash_all_action_types_contribute_to_balance` — Capital df with Cash rows for deposit, trading, income, fee actions (TV=+1000, −200, +50, −10); Cash cumulative `book_cost == 840.0`

  **TestOutputSchema**:
  - `test_output_columns_correct` — Any valid input; result columns exactly equal `OUTPUT_COLUMNS` in order
  - `test_output_sorted_by_date_then_sub_account` — Multiple sub-accounts on multiple dates; result rows sorted ascending by date then sub_account alphabetically
  - `test_one_row_per_date_sub_account` — Two capital dfs each contributing one row for same (date, sub_account); output has exactly one row for that pair
  - `test_empty_inputs_returns_empty_df` — `run(capital_dfs=[], income_dfs=[])` → empty DataFrame with `OUTPUT_COLUMNS`

- [X] T022 [P] [US3] Add 3 US3 BDD scenarios to `tests/features/create_subaccount_ledger.feature`:
  ```gherkin
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
  ```

- [X] T023 [P] [US3] Add to `tests/features/steps/create_subaccount_ledger_steps.py`:
  - `@scenario` bindings: `test_cash_income_excluded`, `test_cash_qty_equals_book_cost`, `test_missing_capital_file_error`, `test_output_columns_correct_order`
  - `@given('a path to a non-existent capital ledger file')` — stores a non-existent Path in `state["bad_capital_path"]`
  - `@when('I run create_subaccount_ledger with that non-existent capital path')` — runs pipeline command with the bad path; captures `returncode`, `stdout`, and `stderr` in `state`
  - `@then(parsers.parse('the exit code is non-zero'))` — asserts `state["returncode"] != 0`
  - `@then('the error output mentions the missing file path')` — asserts that the file name from `state["bad_capital_path"]` appears in `state["stderr"]` or `state["stdout"]`
  - `@then(parsers.parse('there is no Cash row with date "{date}" in the output'))` — reads output XLSX; asserts no row where `sub_account=="Cash"` AND `date==date`
  - `@then(parsers.parse('the Cash row on "{date}" has quantity equal to book_cost'))` — reads output; finds Cash row at date; asserts `row.quantity == pytest.approx(row.book_cost)`
  - `@then(parsers.parse('the Cash row on "{date}" has total_income {expected:f}'))` — asserts `row.total_income == pytest.approx(expected)`
  - `@then('the output XLSX has exactly the columns date, sub_account, book_cost, quantity, total_income in that order')` — reads output XLSX; asserts `list(df.columns) == ["date", "sub_account", "book_cost", "quantity", "total_income"]`

- [X] T024 [US3] Confirm `TestCashHandling` and `TestOutputSchema` tests FAIL (RED): run `python -m pytest tests/unit/create_subaccount_ledger/test_engine.py::TestCashHandling tests/unit/create_subaccount_ledger/test_engine.py::TestOutputSchema -v` — all 9 must fail

### Implementation for User Story 3

- [X] T025 [US3] Add **Pass 3** and merge logic to `src/modes/create_subaccount_ledger/engine.py`:
  1. **Pass 3 — Cash balance**: from `capital_dfs` only, filter `sub_account == CASH_SUB_ACCOUNT`; group by `date`, sum `TV`; sort by `date`; cumsum → `cash_balance`; produce Cash rows: `sub_account=CASH_SUB_ACCOUNT`, `book_cost=cash_balance`, `quantity=cash_balance`, `total_income=0.0`
  2. **Merge**: concatenate equity+income result (from Passes 1+2) with Cash rows (Pass 3)
  3. Sort final result by `(date, sub_account)` ascending
  4. **Empty guard**: if all three passes return no rows, return `pd.DataFrame(columns=OUTPUT_COLUMNS)`
  5. Ensure `run()` signature remains `run(self, capital_dfs: list[pd.DataFrame], income_dfs: list[pd.DataFrame]) -> pd.DataFrame`

- [X] T026 [US3] Update `src/modes/create_subaccount_ledger/mode.py` to strip Cash rows from income DataFrames before calling the engine:
  - After loading income DataFrames, filter each: `df[df[LEDGER_COL_SUB_ACCOUNT] != CASH_SUB_ACCOUNT]`
  - Pass the filtered income DataFrames to `engine.run()`
  - (Capital DataFrames are passed unfiltered — the engine uses all their Cash rows for Pass 3)

- [X] T027 [US3] Confirm all tests pass (GREEN): run `python -m pytest tests/unit/create_subaccount_ledger/ tests/features/steps/create_subaccount_ledger_steps.py -v` — all 21 unit tests (8 + 4 + 5 + 4) and all 8 BDD scenarios must pass; no existing test regressions

**Checkpoint**: All three user stories complete and tested. Full sub-account ledger functionality is live.

---

## Phase 6: Polish & Quality Gates

**Purpose**: Mandatory constitution gates — all four must be green before the feature is considered done.

- [X] T028 [P] Run `mypy --strict src/` — zero errors required (Constitution gate III); fix any type annotation gaps in `constants.py`, `engine.py`, `mode.py`
- [X] T029 [P] Run `ruff check . && ruff format --check .` — zero violations required (Constitution gate IV); fix any style issues in the three new source files
- [X] T030 Verify structured logging in `src/modes/create_subaccount_ledger/mode.py` covers Constitution gate VI: (1) correlation_id logged at mode entry; (2) number of capital and income input files logged; (3) rows_written and COMPLETION_MSG logged at exit
- [X] T031 Run full pytest suite `python -m pytest` — zero regressions; confirm total test count increases by 31 from Feature 013 baseline (393 → 424: 22 unit tests including T033 performance test + 8 BDD scenarios + 1 parametric variant)
- [ ] T032 Validate quickstart.md scenario: run `create_subaccount_ledger` against a real capital ledger output (e.g. `HL_ISA_Capital_Ledger.xlsx`) and inspect the output XLSX — verify columns, sort order, and that Cash rows have `quantity == book_cost`
- [X] T033 Validate SC-004 performance: construct a synthetic 1,000-row ledger DataFrame (use `create_fixtures.py` or a pytest fixture; mix of buy/sell/dividend/Cash rows across 20 sub-accounts and 50 dates); time `SubAccountLedgerEngine().run([df], [])` with `time.perf_counter()` and assert elapsed < 10.0 seconds. Add as a standalone test in `tests/unit/create_subaccount_ledger/test_engine.py` named `test_performance_1000_rows_under_10_seconds`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (directories must exist)
- **Phase 3 (US1)**: Depends on Phase 2 (constants.py + fixtures must exist); T010 depends on T007/T008/T009; T011 depends on T010; T012/T013 can follow T011; T014 validates T011+T012+T013
- **Phase 4 (US2)**: Depends on Phase 3 complete; T018 depends on T015/T016/T017; T019 depends on T018; T020 validates T019
- **Phase 5 (US3)**: Depends on Phase 4 complete; T024 depends on T021/T022/T023; T025 depends on T024; T026 depends on T025; T027 validates T025+T026
- **Phase 6 (Polish)**: Depends on Phase 5 complete (T027 green)

### Within Each User Story

```
Tests (parallel) → Confirm FAIL → Implement (sequential) → Confirm PASS
```

### Parallel Opportunities

| Parallel Group | Tasks | Files |
|---|---|---|
| Setup | T001, T002, T003 | 3 different dirs |
| US1 test writing | T007, T008, T009 | 3 different files |
| US2 test writing | T015, T016, T017 | 3 different files |
| US3 test writing | T021, T022, T023 | 3 different files |
| Quality gates | T028, T029 | Independent tools |

---

## Implementation Strategy

### MVP (User Story 1 only)

1. T001–T003: Setup
2. T004–T006: Foundational (constants + fixtures)
3. T007–T014: US1 (equity positions)
4. **STOP and VALIDATE**: single and multi-ledger equity output is correct

### Incremental Delivery

1. Setup + Foundational → T001–T006
2. US1 complete → equity positions working (MVP)
3. US2 complete → dividend income added to output
4. US3 complete → Cash balance + income exclusion + error handling
5. Polish → constitution gates green, full suite green

---

## Notes

- The engine's `run()` method accepts `income_dfs` that may still contain Cash rows during the US2 phase (before T026 is implemented). This is safe: Passes 1 and 2 both filter `sub_account != CASH_SUB_ACCOUNT`, so income Cash rows are excluded by the engine's own logic. T026 adds explicit defensive stripping at the mode level per FR-007 ("excluded entirely from processing") once US3 is implemented.
- Test `test_cash_from_income_df_excluded` (T021) verifies the engine's own Pass 3 logic by passing `income_dfs=[df_with_cash_income_row]` — Pass 3 only reads capital_dfs, so the income Cash row produces no Cash output. The complementary BDD scenario in T022 validates the end-to-end flow with mode.py's T026 stripping also active.
- The `test_equity_from_income_df_included` unit test (T007) verifies that non-Cash equity rows from income DFs are included for `book_cost`/`quantity`. This works because equity buy/sell/lodgement are listed action types in FR-009 — they are included regardless of which input list they came from. The FR-009 exception clause applies only to the Cash sub-account.
- Transaction ID ordering: the engine sorts by `date` (not Transaction ID) before cumsumming — avoids the bug fixed in Feature 014's predecessor (Feature 013 lodgement companions had high Transaction IDs despite early dates).
- Total tasks: 33 | Unit tests: 22 (8 + 4 + 5 + 4 + 1 perf) | BDD scenarios: 8 | Parallel task groups: 5
