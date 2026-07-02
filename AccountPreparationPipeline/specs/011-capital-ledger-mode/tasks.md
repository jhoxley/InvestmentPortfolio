# Tasks: Capital Ledger Mode

**Input**: Design documents from `specs/011-capital-ledger-mode/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓

**Tests**: Tests are MANDATORY per the project constitution. Every user story includes Gherkin
BDD feature files (`tests/features/`) and `pytest` unit tests (`tests/unit/`). Tests MUST be
written and confirmed failing BEFORE implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths are included in all task descriptions

---

## Phase 1: Setup

**Purpose**: Confirm starting state and scaffold the new module directories.

- [X] T001 Run `.venv/Scripts/python -m pytest tests/ -q` to record the baseline test count
  before any changes are made. Record the count for comparison at T024.

- [X] T002 [P] Create the new module package: make directory
  `src/modes/create_capital_ledger/` and add an empty
  `src/modes/create_capital_ledger/__init__.py`.

- [X] T003 [P] Create `src/modes/create_capital_ledger/constants.py` with all named constants
  from `data-model.md`:
  - `CAPITAL_ACTION_DEPOSIT = "deposit"`
  - `CAPITAL_ACTION_INCOME = "income"`
  - `CAPITAL_ACTION_BUY = "buy"`
  - `CAPITAL_ACTION_SELL = "sell"`
  - `CAPITAL_LEDGER_ACTIONS: frozenset[str] = frozenset({"deposit", "income", "buy", "sell"})`
  - `CAPITAL_COL_DATE = "date"`
  - `CAPITAL_COL_CAPITAL = "capital"`
  - `CAPITAL_COL_INCOME = "income"`
  - `CAPITAL_COL_BOOK_VALUE = "book_value"`
  - `CAPITAL_LEDGER_OUTPUT_COLUMNS: list[str] = ["date", "capital", "income", "book_value"]`
  - `LOG_CCL_CORRELATION_ID = "correlation_id"`
  - `COMPLETION_MSG = "Capital ledger written"`
  Full type annotations required; no magic strings elsewhere.

- [X] T004 [P] Create the test unit package: make directory
  `tests/unit/create_capital_ledger/` and add an empty
  `tests/unit/create_capital_ledger/__init__.py`.

- [X] T005 [P] Create test fixture XLSX files in `tests/data/create_capital_ledger/` using a
  short Python script (e.g. run once interactively). All columns from `LEDGER_COLUMNS` =
  `["Transaction ID", "date", "account", "sub_account", "action", "reference",
  "Account Value", "Account Quantity", "Transaction Value", "Transaction Quantity"]`
  must be present. Use placeholder values for non-key columns as listed below.

  **`simple_ledger.xlsx`** — 5 rows:

  | Transaction ID | date       | account    | sub_account | action  | reference | Account Value | Account Quantity | Transaction Value | Transaction Quantity |
  |---------------|------------|------------|-------------|---------|-----------|---------------|-----------------|-------------------|----------------------|
  | `00001-001`   | 2024-01-10 | Test ISA   | Cash        | deposit | Deposit   | 5000.00       | 5000.00         | 5000.00           | 5000.00              |
  | `00002-001`   | 2024-02-15 | Test ISA   | Cash        | income  | Commission| 5120.00       | 5120.00         | 120.00            | 120.00               |
  | `00003-001`   | 2024-03-20 | Test ISA   | Fund A      | buy     | B00001    | 4120.00       | 10.00           | -1000.00          | 10.00                |
  | `00004-001`   | 2024-03-20 | Test ISA   | Fund B      | buy     | B00002    | 2120.00       | 20.00           | -2000.00          | 20.00                |
  | `00005-001`   | 2024-04-10 | Test ISA   | Fund A      | sell    | S00001    | 2920.00       | 5.00            | 800.00            | -5.00                |

  **`mixed_actions_ledger.xlsx`** — same 5 rows as above plus 2 extra rows that must be
  excluded from all capital calculations:

  | Transaction ID | date       | account  | sub_account | action   | reference     | Account Value | Account Quantity | Transaction Value | Transaction Quantity |
  |---------------|------------|----------|-------------|----------|---------------|---------------|-----------------|-------------------|----------------------|
  | `00006-001`   | 2024-03-20 | Test ISA | Cash        | trading  | B00001-offset | 3120.00       | 3120.00         | 1000.00           | 1000.00              |
  | `00007-001`   | 2024-02-15 | Test ISA | Fund C      | dividend | ST DIV        | 50.00         | 50.00           | 50.00             | 50.00                |

  Create with: `df.to_excel(path, index=False, engine="openpyxl")`. Store the creation script
  at `tests/data/create_capital_ledger/create_fixtures.py` for reproducibility.

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Create stub implementations that allow tests to import the module (so they fail with
`AssertionError`, not `ImportError`), and register the mode so the CLI accepts it.

**⚠️ CRITICAL**: Tests in Phase 3 depend on being able to import `CapitalLedgerEngine` and
`CreateCapitalLedgerMode`. These stubs must exist before test files are written.

- [X] T006 Create stub `src/modes/create_capital_ledger/engine.py` containing:
  ```python
  from __future__ import annotations
  import pandas as pd

  class CapitalLedgerEngine:
      def run(self, ledger_df: pd.DataFrame) -> pd.DataFrame:
          raise NotImplementedError
  ```
  Full type annotations and `from __future__ import annotations` required.

- [X] T007 Create stub `src/modes/create_capital_ledger/mode.py` containing a
  `CreateCapitalLedgerMode` class with `name = "create_capital_ledger"`,
  `description = "..."`, `register_arguments()`, and `execute()` that returns
  `EXIT_INVALID_ARGS` — mirroring the structure of `src/modes/create_ledger/mode.py`.

- [X] T008 Register `CreateCapitalLedgerMode` in `pipeline.py`: add
  `from src.modes.create_capital_ledger.mode import CreateCapitalLedgerMode` to imports
  and `registry.register(CreateCapitalLedgerMode())` to `_build_registry()`.
  Run `python pipeline.py --help` and confirm `create_capital_ledger` appears in the
  mode list.

**Checkpoint**: `python pipeline.py create_capital_ledger --help` exits 0 and shows argument
help. Stub engine raises `NotImplementedError`. Foundation ready for test writing.

---

## Phase 3: User Story 1 — Generate Date-Level Capital Summary (Priority: P1) 🎯 MVP

**Goal**: `create_capital_ledger` reads a ledger XLSX, filters to the four action types,
accumulates running totals per date with forward-fill, and writes one row per date to the output.

**Independent Test**: Run `create_capital_ledger` against `tests/data/create_capital_ledger/simple_ledger.xlsx`.
Verify the output has 4 rows (dates: 2024-01-10, 2024-02-15, 2024-03-20, 2024-04-10), that
`capital=5000` on all rows ≥ 2024-01-10, `income=120` on all rows ≥ 2024-02-15, and
`book_value` is `0 → 0 → -3000 → -2200` across the four dates.

### Tests for User Story 1 ⚠️ (write FIRST — confirm they FAIL before implementing)

- [X] T009 [P] [US1] Create BDD step definitions file
  `tests/features/steps/create_capital_ledger_steps.py` **first** (before the feature file),
  so pytest-bdd can collect scenarios without raising `StepDefinitionNotFoundError`. The file
  must contain:
  - `@scenario` bindings for all five scenarios listed in T010 (names must match exactly once
    the feature file is written).
  - Skeleton `@given`, `@when`, `@then` step functions that raise `NotImplementedError` so
    BDD tests fail with a clear error at the step level, not a collection error.
  - `DATA_DIR = Path(__file__).parent.parent.parent / "data" / "create_capital_ledger"`
  - `FEATURE_FILE = str(Path(__file__).parent.parent / "create_capital_ledger.feature")`
  Reuse the import and subprocess pattern from
  `tests/features/steps/consolidate_journals_steps.py`.

- [X] T010 [P] [US1] Create BDD feature file `tests/features/create_capital_ledger.feature`
  with the following scenarios (Gherkin syntax, matching existing feature file style).
  Scenario names must exactly match the `@scenario` bindings written in T009:
  - **Scenario**: "Deposit rows accumulate in capital column"
    — Given `simple_ledger.xlsx`, When `create_capital_ledger` runs, Then row for 2024-01-10
    has capital=5000, row for 2024-02-15 has capital=5000 (carry-forward), income=120, book_value=0.
  - **Scenario**: "Buy and sell rows accumulate in book_value column"
    — Given `simple_ledger.xlsx`, When `create_capital_ledger` runs, Then row for 2024-03-20
    has book_value=-3000, row for 2024-04-10 has book_value=-2200.
  - **Scenario**: "Non-qualifying action rows are excluded from all columns"
    — Given `mixed_actions_ledger.xlsx` (has trading and dividend rows), When run, Then output
    row count equals 4 (same as simple_ledger) and no column value reflects the trading/dividend
    transaction amounts.
  - **Scenario**: "Output has one row per unique date in chronological order"
    — Given `simple_ledger.xlsx`, When run, Then output has exactly 4 rows in ascending date order.
  - **Scenario**: "Mode exits with non-zero code when input file does not exist"
    — Given a path to a non-existent file, When `create_capital_ledger` runs, Then exit code is
    non-zero.

- [X] T011 [P] [US1] Create unit test file
  `tests/unit/create_capital_ledger/test_engine.py` with class `TestCapitalLedgerEngine`.
  Each test builds a minimal `pd.DataFrame` matching the ledger schema and calls
  `CapitalLedgerEngine().run(df)`. Required tests:
  - `test_deposit_rows_accumulate_capital` — two deposit rows → capital cumsum correct
  - `test_income_rows_accumulate_income` — two income rows → income cumsum correct
  - `test_buy_sell_rows_accumulate_book_value` — buy + sell → net book_value correct
  - `test_forward_fill_capital_on_dates_with_no_deposit` — date with no deposit shows prior capital
  - `test_forward_fill_all_columns_start_at_zero` — first date with only a buy shows capital=0, income=0
  - `test_non_qualifying_actions_excluded` — trading and dividend rows produce no contribution
  - `test_one_row_per_date_in_output` — two buy rows on same date → single output row for that date
  - `test_empty_result_when_no_qualifying_rows` — ledger with only trading rows → empty DataFrame
  - `test_output_columns` — output has exactly `["date", "capital", "income", "book_value"]`
  - `test_transaction_id_order_used_for_accumulation` — two buys on same date, Transaction IDs
    `00003-001` and `00004-001`; both contribute to book_value on that date correctly
  Import `CapitalLedgerEngine` from `src.modes.create_capital_ledger.engine` and the required
  ledger columns from `src.modes.create_ledger.constants`.

### Confirm tests FAIL (Red phase)

- [X] T012 [US1] Run:
  ```
  .venv/Scripts/python -m pytest tests/unit/create_capital_ledger/ tests/features/ -v
  ```
  **Expected Red-phase failures:**
  - `TestCapitalLedgerEngine` tests: `NotImplementedError` (stub engine raises it)
  - BDD scenarios: `NotImplementedError` from skeleton step functions in T009 — this is the
    correct Red-phase failure (not `StepDefinitionNotFoundError`, which would indicate the
    step file was not written first per T009). If you see `StepDefinitionNotFoundError`,
    complete T009 before re-running.
  Record the failure output.

### Implementation for User Story 1

- [X] T013 [US1] Implement `CapitalLedgerEngine.run()` in
  `src/modes/create_capital_ledger/engine.py`. Full algorithm:
  1. Validate input has `Transaction ID`, `date`, `action`, `Transaction Value` columns;
     raise `ValueError` if missing.
  2. Cast `Transaction ID` to string before sorting:
     `df[LEDGER_COL_TRANSACTION_ID] = df[LEDGER_COL_TRANSACTION_ID].astype(str)`
     This prevents openpyxl's numeric coercion from silently breaking the zero-padded
     lexicographic sort order (e.g., `00001-001` read as a float would lose its leading zeros).
     Sort input by `Transaction ID` ascending (string sort — Transaction IDs are zero-padded and
     sort correctly as strings).
  3. Filter to rows where `action` is in `CAPITAL_LEDGER_ACTIONS`.
  4. If the filtered DataFrame is empty, return an empty DataFrame with
     `CAPITAL_LEDGER_OUTPUT_COLUMNS`.
  5. Map each row's `Transaction Value` to the correct column: `deposit` → `capital_contrib`,
     `income` → `income_contrib`, `buy`/`sell` → `bv_contrib`; all others zero.
  6. Group by `date` (keeping chronological order from the Transaction ID sort), sum each
     contribution column per date.
  7. Take cumulative sum across dates for each column.
  8. Fill any remaining NaN with 0.0 (handles first-date gaps), then forward-fill is implicit
     since cumsum carries values forward.
  9. Return DataFrame with columns `["date", "capital", "income", "book_value"]`.
  Full type annotations, no magic strings (use constants), structured logging at DEBUG level.

- [X] T014 [US1] Implement the full `CreateCapitalLedgerMode` in
  `src/modes/create_capital_ledger/mode.py`:
  - `register_arguments()`: two positional args `input_path` (INPUT_PATH) and
    `output_path` (OUTPUT_PATH) — identical pattern to `CreateLedgerMode`.
  - `execute()`: validate `input_path` exists (return `EXIT_INVALID_ARGS` + log error if not);
    call `pd.read_excel(input_path, engine="openpyxl")`; call `CapitalLedgerEngine().run(df)`;
    write result to `output_path` via `pd.ExcelWriter` with `openpyxl` engine; log start, row
    count, and `COMPLETION_MSG` with correlation ID.
  Mirror error handling and logging patterns from `src/modes/create_ledger/mode.py`.

### Confirm tests PASS (Green phase)

- [X] T015 [US1] Run:
  ```
  .venv/Scripts/python -m pytest tests/unit/create_capital_ledger/ tests/features/create_capital_ledger.feature -v
  ```
  All `TestCapitalLedgerEngine` unit tests and all BDD scenarios must pass. Record final
  pass count.

**Checkpoint**: US1 complete. `create_capital_ledger` generates correct date-level capital
summaries. Existing test suite unchanged.

---

## Phase 4: User Story 2 — Pipeline Integration for Capital Accounts (Priority: P2)

**Goal**: `run_pipeline.ps1` runs `create_capital_ledger` as step 3 for HL SIPP and HL ISA
only. Income accounts (HL SIPP Income, HL ISA Income) are unaffected.

**Independent Test**: Run `run_pipeline.ps1`. Confirm `HL_SIPP_Capital_Ledger.xlsx` and
`HL_ISA_Capital_Ledger.xlsx` are created (or updated) in `$InvestmentsDir`. Confirm no
equivalent file exists for Income accounts. Confirm exit code is 0.

### Tests for User Story 2 ⚠️ (write FIRST — confirm they FAIL before implementing)

- [X] T016 [P] [US2] Add a BDD scenario to `tests/features/create_capital_ledger.feature`
  covering the CLI invocation that `run_pipeline.ps1` will use:
  - **Scenario**: "Pipeline mode accepts input and output path arguments"
    — Given a valid ledger XLSX (from T005 fixture), When `create_capital_ledger <input> <output>`
    is run via `pipeline.py`, Then exit code is 0 and the output XLSX is created with the correct
    columns.
  Add the `@scenario` binding and any new step definitions needed to
  `tests/features/steps/create_capital_ledger_steps.py` (should already be largely covered
  by T011 steps).

### Confirm tests FAIL

- [X] T017 [US2] Run:
  ```
  .venv/Scripts/python -m pytest tests/features/create_capital_ledger.feature::pipeline_mode_scenario -v
  ```
  (or run the full BDD suite and confirm only the new scenario fails). The scenario should
  already pass after US1 if mode registration was done in T008 — if so, mark this task
  complete and proceed.

### Implementation for User Story 2

- [X] T018 [US2] Update `run_pipeline.ps1`: add `IsCapitalAccount = $true` and
  `CapitalLedgerPath` keys to the HL SIPP and HL ISA account hashtables:
  ```powershell
  @{
      Name              = "HL SIPP"
      IsCapitalAccount  = $true
      CapitalLedgerPath = Join-Path $InvestmentsDir "HL_SIPP_Capital_Ledger.xlsx"
      ...
  }
  @{
      Name              = "HL ISA"
      IsCapitalAccount  = $true
      CapitalLedgerPath = Join-Path $InvestmentsDir "HL_ISA_Capital_Ledger.xlsx"
      ...
  }
  ```
  Income account hashtables receive `IsCapitalAccount = $false` (or omit the key and guard
  with `$account.IsCapitalAccount -eq $true`).

- [X] T019 [US2] Add step 3 block inside the `run_pipeline.ps1` execution loop, immediately
  after step 2 (`create_ledger`), guarded by `$account.IsCapitalAccount -eq $true`:
  ```powershell
  # ── Step 3: Build capital summary from ledger ──────────────────────────────
  if (-not $failed -and $account.IsCapitalAccount -eq $true) {
      Write-Host ""
      Write-Host "  [3/3] create_capital_ledger" -ForegroundColor Yellow
      Write-Host "        $($account.LedgerPath)"
      Write-Host "     -> $($account.CapitalLedgerPath)"
      & $PythonExe $PipelinePy create_capital_ledger `
          $account.LedgerPath `
          $account.CapitalLedgerPath
      if ($LASTEXITCODE -ne 0) {
          Write-Host "  FAILED: create_capital_ledger exited with code $LASTEXITCODE" -ForegroundColor Red
          $failed = $true
      }
  }
  ```
  Update the step label for step 2 from `[2/2]` to `[2/3]` when `IsCapitalAccount` is true
  (or keep labels static at `[2/2]` / `[3/3]` — either is acceptable). Ensure the existing
  `# ── Future steps:` comment block is preserved below the new step.

- [ ] T020 [US2] Manual verification: run `.\run_pipeline.ps1` against the real investment
  data in `C:\Users\jhoxl\OneDrive\Investments\`. Confirm:
  1. `HL_SIPP_Capital_Ledger.xlsx` is created/updated in `$InvestmentsDir`.
  2. `HL_ISA_Capital_Ledger.xlsx` is created/updated in `$InvestmentsDir`.
  3. No capital ledger file for HL SIPP Income or HL ISA Income.
  4. All four accounts complete step 1 and step 2; only HL SIPP and HL ISA run step 3.
  5. Exit code is 0.
  6. Open each capital ledger XLSX and verify: one row per date, `capital` increases only on
     deposit dates, `book_value` is negative when invested capital exceeds proceeds.

**Checkpoint**: US2 complete. Pipeline produces capital ledgers for both capital accounts.
Income accounts unaffected.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates per project constitution.

- [X] T021 [P] Run `mypy --strict src/` — zero errors required (Constitution gate III).
  Pay attention to `src/modes/create_capital_ledger/` (all three files).

- [X] T022 [P] Run `ruff check .` and `ruff format --check .` — zero violations required
  (Constitution gate IV). Fix any E501 or import-sort violations introduced.

- [X] T023 Run full test suite:
  ```
  .venv/Scripts/python -m pytest tests/ -v
  ```
  All tests must pass. New count must be ≥ baseline (T001) + tests added in T009 + T010.
  Confirm zero regressions in existing `create_ledger`, `consolidate_journals`, and BDD suites.

- [X] T024 Verify structured logging: open `src/modes/create_capital_ledger/mode.py` and
  confirm log records include: start event (with `input_path`, `output_path`,
  `correlation_id`), completion event (with `rows_written`, `correlation_id`), and error
  event on invalid input (with `detail`). Confirm `COMPLETION_MSG` constant is used (not a
  magic string). No `print()` statements in any production file.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run T001–T005 immediately; T002–T005 are parallel
- **Foundational (Phase 2)**: Depends on Phase 1 (constants.py must exist before stubs); T006–T008
  must run sequentially (constants → engine stub → mode stub → register)
- **US1 (Phase 3)**: Depends on Phase 2 complete; T009–T011 can run in parallel after T007;
  T012 confirms Red; T013–T014 implement; T015 confirms Green
- **US2 (Phase 4)**: Depends on Phase 3 complete (mode must work before pipeline invokes it)
- **Polish (Phase 5)**: Depends on Phase 4 complete

### Within Each User Story

1. Write tests (T009–T011) → confirm they FAIL (T012)
2. Implement (T013–T014) → confirm tests PASS (T015)
3. No regressions

### Parallel Opportunities

- T002, T003, T004, T005 (setup file creation) — all parallel, different directories
- T009, T010, T011 (write tests for US1) — all parallel, different files
- T021, T022 (mypy + ruff) — parallel, independent tools

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational stubs (T006–T008)
3. Write US1 tests (T009–T011), confirm Red (T012)
4. Implement US1 (T013–T014), confirm Green (T015)
5. **STOP and VALIDATE**: `create_capital_ledger` works correctly for a sample ledger
6. Polish US1 (T021–T024) before adding pipeline integration

### Full Delivery

Add Phase 4 (US2) after MVP validation — `run_pipeline.ps1` update and manual end-to-end verification.

---

## Notes

- **Total tasks**: 24 (T001–T024)
- **US1 tasks**: 7 (T009–T015)
- **US2 tasks**: 5 (T016–T020)
- **Polish tasks**: 4 (T021–T024)
- **[P] tasks** (parallelisable): T002, T003, T004, T005, T009, T010, T011, T016, T021, T022
- New source files: `constants.py`, `engine.py`, `mode.py`, `__init__.py` (all in
  `src/modes/create_capital_ledger/`)
- Modified files: `pipeline.py` (mode registration), `run_pipeline.ps1` (step 3)
- The `Transaction Value` column in the input ledger is already sign-adjusted by `create_ledger`
  (buys are negative, sells are positive) — no additional sign logic needed in `engine.py`
