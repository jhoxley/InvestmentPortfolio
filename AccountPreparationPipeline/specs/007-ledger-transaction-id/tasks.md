# Tasks: Ledger Transaction ID

**Input**: Design documents from `specs/007-ledger-transaction-id/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Tests are MANDATORY per the project constitution. Every user story MUST include BDD
Gherkin scenarios (`tests/features/`) and `pytest` unit tests (`tests/unit/`). Tests MUST be
written and confirmed failing BEFORE implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (truly different files or independent operations)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task

---

## Phase 1: Setup

**Purpose**: Correct the existing schema test so it accurately reflects the upcoming column
addition. Also update the quickstart sort key to match the clarification (4-tuple including
`account`). These are semantic corrections done before the RED-GREEN cycle begins.

- [x] T001 In `tests/features/create_ledger.feature` (line 78): change scenario title from
  `"Output contains exactly nine columns in defined order"` to
  `"Output contains exactly ten columns in defined order"`. In
  `tests/features/steps/create_ledger_steps.py`: (a) add `"Transaction ID"` as the first element
  of the module-level `LEDGER_COLUMNS` list (line 14); (b) update the `@then` decorator on
  `check_nine_column_schema` to `"the output has exactly ten columns in the defined order"` and
  rename the function to `check_ten_column_schema`. This makes the existing schema scenario RED
  immediately — confirms the test is honest before new work begins.

- [x] T002 In `specs/007-ledger-transaction-id/quickstart.md`: replace all occurrences of
  `(date, sub_account, reference)` with `(date, account, sub_account, reference)` to match the
  clarification recorded in spec.md. (Documentation fix — no code impact.)

---

## Phase 2: Foundational

**Purpose**: No blocking shared infrastructure is required. Existing `LedgerEngine`,
`CreateLedgerMode`, and constants are the foundation. Phase 2 is intentionally empty — proceed
directly to user story phases.

---

## Phase 3: User Stories 1 & 2 — Transaction ID Column + Canonical Sort Order (Priority: P1) 🎯 MVP

**Goal**: Add a `Transaction ID` column (`NNNNN-001` on first run) whose canonical sort order
`(date, account, sub_account, reference)` ensures the per-position ledger invariant holds for any
row ordering including same-date Cash offset rows. US1 and US2 share the same implementation
change (new column + sort key), so their tests and implementation are grouped together.

**Independent Test**:
```powershell
python -m pytest tests/unit/create_ledger/ tests/features/ tests/integration/ -v -k "ledger or transaction"
```
All US1+US2 tests must be GREEN after T011. Zero failures.

### Tests for US1 + US2 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T008)

- [x] T003 [US1] In `tests/features/create_ledger.feature`: add two new scenarios below the
  existing ones —
  (1) `"First-time run produces Transaction ID column with sequential IDs"` — Given single buy
  event, When create_ledger, Then Transaction ID column exists and first row value is `"00001-001"`.
  (2) `"Transaction IDs are sequential with 001 suffix on first run"` — Given journal with 3
  events on different dates, When create_ledger, Then Transaction IDs are `"00001-001"`,
  `"00002-001"`, `"00003-001"` in ascending row order.
  In `tests/features/steps/create_ledger_steps.py`: add `@scenario` bindings for both new
  scenarios; add `@then("the Transaction ID column exists and first row value is 00001-001")`
  step asserting `out_df["Transaction ID"].iloc[0] == "00001-001"` and `"Transaction ID" in out_df.columns`;
  add `@then("the Transaction IDs are 00001-001 00002-001 00003-001 in ascending row order")`
  step asserting `list(out_df["Transaction ID"]) == ["00001-001", "00002-001", "00003-001"]`.

- [x] T004 [P] [US1] Create `tests/unit/create_ledger/test_transaction_id.py` with class
  `TestFirstTimeAssignment` containing:
  - `test_three_rows_get_sequential_ids`: build a 3-row DataFrame with columns
    `["date", "account", "sub_account", "action", "reference", "value", "quantity"]` sorted by
    `(date, account, sub_account, reference)`, call `TransactionIDAssigner().assign(df, {})`,
    assert result equals `pd.Series(["00001-001", "00002-001", "00003-001"])`.
  - `test_single_row_gets_00001_001`: 1-row DataFrame, assert `assign(df, {}).iloc[0] == "00001-001"`.
  - `test_100_rows_all_have_001_suffix`: 100-row DataFrame with unique references, assert all
    values match `r"^\d{5}-001$"` and last value is `"00100-001"`.
  - `test_empty_df_returns_empty_series`: empty DataFrame, assert result is empty Series.

- [x] T005 [P] [US1] In `tests/integration/test_create_ledger_e2e.py`: add
  `test_transaction_id_column_present_on_first_run` — build a 3-row journal (B001 on 2024-01-01,
  B002 on 2024-01-02, B003 on 2024-01-03, all same account/sub_account), run pipeline, assert
  `"Transaction ID" in out_df.columns`, `out_df["Transaction ID"].iloc[0] == "00001-001"`,
  `out_df["Transaction ID"].iloc[2] == "00003-001"`, and no null values. Also use
  `openpyxl.load_workbook(output_path)` to assert `ws.cell(row=2, column=1).number_format == "@"`
  (belt-and-suspenders check that the Transaction ID column is XLSX-formatted as text, verifying
  the `@` format applied in T012).

- [x] T006 [US2] In `tests/features/create_ledger.feature`: add scenario
  `"Same-date Cash offsets are ordered by reference to preserve per-position invariant"` — Given
  journal with two buys on 2024-03-15 (B001 value=-1000, B002 value=-500) and their Cash offsets
  (B001-offset value=-1000, B002-offset value=-500) in arbitrary order, When create_ledger, Then
  exit code is 0 and for the Cash rows sorted by Transaction ID the invariant holds
  (`Account Value[row2] = Account Value[row1] + Transaction Value[row2]`).
  In `tests/features/steps/create_ledger_steps.py`: add `@scenario` binding; add
  `@given("a journal with two same-date buys and their Cash offsets")` that creates a 4-row
  journal with rows deliberately NOT in canonical order; add
  `@then("the Cash rows in Transaction ID order satisfy the per-position invariant")` that reads
  output, filters to Cash sub_account, sorts by Transaction ID, and checks the invariant.

- [x] T007 [P] [US2] In `tests/unit/create_ledger/test_engine.py`: add class `TestTransactionIDSort`
  containing:
  - `test_cash_sorts_before_vanguard_same_date`: 2 rows on 2024-01-01 — sub_account="Cash" (action=deposit)
    and sub_account="Vanguard Fund" (action=buy); assert `result.iloc[0]["Transaction ID"] == "00001-001"`
    for the Cash row and `result.iloc[1]["Transaction ID"] == "00002-001"` for Vanguard Fund
    (Cash < Vanguard Fund alphabetically).
  - `test_reference_tiebreaker_within_same_sub_account_date`: 2 rows on 2024-01-01, both Cash, references
    "B001-offset" and "B002-offset"; assert B001-offset gets `"00001-001"` and B002-offset gets `"00002-001"`.
  - `test_account_included_in_sort_key`: 2 rows on 2024-01-01, accounts "ISA" and "SIPP" (both Cash/Deposit);
    assert ISA row (alphabetically first) gets `"00001-001"`.

- [x] T008 [P] [US2] In `tests/integration/test_create_ledger_e2e.py`: add
  `test_same_date_cash_offset_invariant` — build a 4-row journal: ISA/Vanguard Fund/buy B001
  (value=-1000, qty=10) on 2024-03-15; ISA/Vanguard Fund/buy B002 (value=-500, qty=5) on 2024-03-15;
  ISA/Cash/trading B001-offset (value=-1000) on 2024-03-15; ISA/Cash/trading B002-offset (value=-500)
  on 2024-03-15 — input rows in arbitrary (non-canonical) order. Run pipeline. Read output, filter
  Cash rows, sort by `Transaction ID`, assert `out_cash.iloc[1]["Account Value"] == pytest.approx(
  out_cash.iloc[0]["Account Value"] + out_cash.iloc[1]["Transaction Value"])`.

**Checkpoint**: Run `python -m pytest tests/ -v -k "ledger or transaction"` — T001 schema update
and T003–T008 must all FAIL (or import-error). Do NOT proceed to T009 until failures confirmed.

### Implementation for US1 + US2

- [x] T009 [US1] In `src/modes/create_ledger/constants.py`: add
  `LEDGER_COL_TRANSACTION_ID: str = "Transaction ID"` and
  `TRANSACTION_ID_SORT_COLS: list[str] = ["date", "account", "sub_account", "reference"]`;
  add `LEDGER_COL_TRANSACTION_ID` as the first element of `LEDGER_COLUMNS` (shifting all existing
  columns right by one position). The `LEDGER_COLUMNS.index(col_name) + 1` formula in mode.py
  self-corrects for the shift — no change needed there.

- [x] T010 [US1] Create `src/modes/create_ledger/transaction_id.py` with:
  ```python
  class TransactionIDAssigner:
      def assign(
          self,
          df: pd.DataFrame,
          prior_ids: dict[tuple[str, str, str, str], str],
      ) -> pd.Series:
  ```
  First-time case (prior_ids empty): return
  `pd.Series([f"{i+1:05d}-001" for i in range(len(df))], index=df.index, dtype=str)`.
  Empty df case: return `pd.Series([], dtype=str)`.
  Re-run case: not yet implemented (returns first-time IDs for all rows — intentionally incomplete
  until T020). After assigning first-time IDs, log:
  `_logger.debug("Transaction IDs assigned", extra={"count": len(df), "mode": "first_time"})`.
  Include full type annotations; import `from __future__ import annotations`.

- [x] T011 [US1][US2] In `src/modes/create_ledger/engine.py`: (a) update
  `sort_values(["account", "sub_account", "date"], kind="stable")` → 
  `sort_values(TRANSACTION_ID_SORT_COLS, kind="stable")`; (b) add `prior_ids` parameter to `run()`:
  `prior_ids: dict[tuple[str, str, str, str], str] | None = None`; (c) after the cumsum block,
  call `tid_series = TransactionIDAssigner().assign(df, prior_ids or {})`; (d) assign
  `df[LEDGER_COL_TRANSACTION_ID] = tid_series`; (e) return `df[LEDGER_COLUMNS]`. Add required
  imports: `LEDGER_COL_TRANSACTION_ID`, `TRANSACTION_ID_SORT_COLS` from constants;
  `TransactionIDAssigner` from `src.modes.create_ledger.transaction_id`.

- [x] T012 [US1] In `src/modes/create_ledger/mode.py`: in the `with pd.ExcelWriter` block, add
  a *separate* cell-iteration block for the Transaction ID column — do NOT extend the existing
  numeric-format loop (which applies `#,##0.00` / `#,##0.0000`); Transaction ID requires `"@"`
  (Excel text format), not a numeric format. Find the column index with
  `col_idx = LEDGER_COLUMNS.index(LEDGER_COL_TRANSACTION_ID) + 1` and set `cell.number_format = "@"`
  for all data rows in that column. Add `LEDGER_COL_TRANSACTION_ID` to the import from
  `src.modes.create_ledger.constants`.

- [x] T013 [US2] In `tests/features/steps/create_ledger_steps.py`: update the two step functions
  that sort the input DataFrame for column-order comparison —
  `check_action_unchanged` and `check_reference_unchanged` (lines ~334–350): change
  `sort_values(["account", "sub_account", "date"], kind="stable")` to
  `sort_values(["date", "account", "sub_account", "reference"], kind="stable")` to match the
  engine's new canonical sort order.

**Checkpoint**: Run `python -m pytest tests/ -v -k "ledger or transaction"` — all T003–T008 tests
and T001 schema test must be GREEN. Zero regressions in existing tests. Confirm before Phase 4.

---

## Phase 4: User Story 3 — Re-Run ID Preservation (Priority: P2)

**Goal**: When `create_ledger` is re-run against a journal that has new events relative to the
prior ledger, existing Transaction IDs are preserved and new rows receive insertion IDs
(`NNNNN-002`, `NNNNN-003`, …) or appended IDs (`(max+K)-001`). Idempotent re-runs produce
identical IDs.

**Independent Test**:
```powershell
python -m pytest tests/unit/create_ledger/test_transaction_id.py -v -k "rerun or idempotent"
python -m pytest tests/integration/ -v -k "rerun or idempotent or preserves"
```
All re-run tests must be GREEN after T022. Zero failures.

### Tests for US3 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T020)

- [x] T014 [US3] In `tests/features/create_ledger.feature`: add three new scenarios —
  (1) `"Re-running with a new row between existing rows assigns suffix-incremented ID"` — Given
  existing ledger with rows 00001-001/00002-001/00003-001 and a new journal event that canonically
  sorts between the first and second, When create_ledger is re-run with the same output path, Then
  the original three IDs are unchanged and the new row gets `"00001-002"`.
  (2) `"Idempotent re-run produces identical Transaction IDs"` — Given existing ledger, When
  create_ledger re-run with same journal, Then all Transaction IDs are unchanged.
  (3) `"New row after all existing rows gets next sequential prefix"` — Given existing ledger with
  last ID 00003-001, new event sorts after all existing, Then new row gets `"00004-001"`.
  In `tests/features/steps/create_ledger_steps.py`: add `@scenario` bindings; add
  `@given("an existing ledger produced from a 3-row journal")` that creates a journal, runs
  create_ledger to produce a real prior ledger XLSX at a fixed path; add `@given("a new journal
  event inserted between the first and second existing rows")` that adds a row with reference
  `"B001a"` on date `2024-01-01` (sorts after B001 on the same date — `"B001a" > "B001"`
  alphabetically — and before B002 which is on `2024-01-02`); add Then steps asserting original
  IDs preserved and new ID value.

- [x] T015 [P] [US3] In `tests/unit/create_ledger/test_transaction_id.py`: add class
  `TestReRunAssignment` containing:
  - `test_existing_rows_preserve_their_ids`: DataFrame with 3 rows all in prior_ids; assert
    `assign(df, prior_ids)` returns the same 3 IDs unchanged.
  - `test_new_row_between_existing_gets_suffix_002`: 3-row df where rows 0 and 2 are in prior_ids
    (as `00001-001` and `00002-001`) and row 1 is new; assert row 1 gets `"00001-002"`.
  - `test_second_insertion_gets_suffix_003`: 3-row df where rows 0 and 2 are in prior_ids
    (mapped to `"00001-001"` and `"00002-001"`); prior_ids also contains an additional entry whose
    key is NOT present in the current df — e.g. `("2024-01-01", "ISA", "Vanguard Fund",
    "B001-absent") → "00001-002"` (simulates a previously inserted row since removed from the
    journal); row 1 is new; assert row 1 gets `"00001-003"` (max suffix for prefix 00001 across
    all prior_ids values is 002, so new suffix = 003).
  - `test_new_row_after_all_existing_gets_next_prefix`: 2-row df, both in prior_ids (00001-001,
    00002-001), plus 1 new row appended; assert new row gets `"00003-001"`.
  - `test_idempotent_rerun_returns_identical_ids`: all rows in prior_ids; assert `assign(df, prior_ids)`
    returns exactly the same IDs as the values in prior_ids.

- [x] T016 [P] [US3] In `tests/integration/test_create_ledger_e2e.py`: add three tests —
  `test_rerun_preserves_existing_ids`: first run produces ledger with 3 rows; second run (same
  journal) — assert all 3 Transaction IDs unchanged.
  `test_rerun_inserts_between_assigns_suffix`: first run produces 3-row ledger with references
  "B001" (2024-01-01), "B002" (2024-01-02), "B003" (2024-01-03) → IDs 00001-001/00002-001/00003-001;
  add a new journal row with reference "B001a" on date 2024-01-01 (canonically sorts after
  B001/2024-01-01 — same date, "B001a" > "B001" alphabetically — and before B002/2024-01-02;
  preceding prior-ID row is B001 → inherits prefix 00001); second run — assert original 3 IDs
  intact and new row gets `"00001-002"`.
  `test_idempotent_rerun`: first and second run on identical journal to same output path — assert
  `list(first_run_df["Transaction ID"]) == list(second_run_df["Transaction ID"])`.

**Checkpoint**: Run `python -m pytest tests/ -v -k "rerun or idempotent or preserves"` — all
T014–T016 tests must FAIL (TransactionIDAssigner re-run logic not yet implemented; prior_ids
ignored). Do NOT proceed to T020 until failures confirmed.

### Implementation for US3

- [x] T020 [US3] In `src/modes/create_ledger/transaction_id.py` `TransactionIDAssigner.assign()`:
  implement the re-run case (when `prior_ids` is non-empty). Algorithm:
  1. Build key tuples: `key = (str(pd.Timestamp(row.date).date()), row.account, row.sub_account, row.reference)` for each row
     (must produce `"YYYY-MM-DD"` strings — same normalization as `_load_prior_ids()` in mode.py; consider
     extracting a shared module-level `_normalise_date(val: object) -> str` helper used in both places to
     guarantee they never diverge).
  2. Walk rows in index order (already sorted by canonical key by engine):
     - If key in prior_ids: use prior ID → record `(prefix_int, suffix_int)` for this slot.
     - If new row:
       a. Find `preceding_prefix` = the 5-digit prefix of the last prior-ID row seen before this position.
          If no prior-ID row has appeared yet, use prefix 1.
       b. `max_suffix` = max suffix already assigned to `preceding_prefix` (scanning both prior_ids
          values and already-assigned IDs in this call).
       c. `new_suffix = max_suffix + 1`. Raise `ValueError` if new_suffix > 999.
       d. Assign `f"{preceding_prefix:05d}-{new_suffix:03d}"`.
     - If new row sorts after ALL existing (prior) rows:
       `max_prefix` = max 5-digit prefix across all prior_ids values.
       Assign next sequential prefix: `f"{max_prefix + assigned_append_count + 1:05d}-001"`.
       Raise `ValueError` if max_prefix + count >= 99999.
  3. Helper `_parse_id(tid: str) -> tuple[int, int]`: splits `"NNNNN-NNN"` → `(int(N), int(N))`.
  Full type annotations required. Zero `Any` usage. Log at DEBUG level if any re-run ID is assigned.

- [x] T021 [US3] In `src/modes/create_ledger/mode.py`: (a) add module-level helper
  `_load_prior_ids(path: Path) -> dict[tuple[str, str, str, str], str]` that:
  - Returns `{}` if `path` does not exist.
  - Reads `path` via `pd.read_excel(path, engine="openpyxl")`.
  - If the file exists but has no `Transaction ID` column: logs `WARNING` and returns `{}`.
  - If unreadable (OSError/Exception): logs `WARNING` with exception detail and returns `{}`.
  - Otherwise builds `{(str(row.date), row.account, row.sub_account, row.reference): row["Transaction ID"]}`
    for each row; ensures date is normalized to string via `str(pd.Timestamp(row.date).date())`.
  (b) In `CreateLedgerMode.execute()`: before `LedgerEngine().run(df)`, call
  `prior_ids = _load_prior_ids(output_path)` and pass `prior_ids=prior_ids` to the engine.
  Log at INFO level: `"Prior ledger read"` with `{"prior_ids_count": len(prior_ids)}` when
  prior_ids is non-empty.

**Checkpoint**: Run `python -m pytest tests/ -v` — all US3 tests plus all prior tests must be
GREEN. Confirm zero regressions.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates and full-suite validation.

- [x] T022 [P] Run `mypy --strict src/ pipeline.py` — zero type errors (Constitution gate III).
  Fix any annotation gaps in `transaction_id.py` (dict key type `dict[tuple[str, str, str, str], str]`,
  return type `pd.Series`, `_parse_id` return `tuple[int, int]`) and `mode.py` (`_load_prior_ids`
  return type, `prior_ids` parameter type).

- [x] T023 [P] Run `ruff check .` — zero violations (Constitution gate IV). Fix any issues in
  new files `transaction_id.py` and any modified files.

- [x] T024 [P] Run `ruff format --check .` — zero violations; auto-fix with `ruff format .` if
  needed (Constitution gate IV).

- [x] T025 Run full test suite `python -m pytest tests/ -v` — zero failures across all three test
  directories (`tests/features/`, `tests/unit/`, `tests/integration/`). Confirm SC-001 through
  SC-005 are covered by passing tests.

- [ ] T026 Validate quickstart.md scenarios manually: run `python pipeline.py create_ledger
  <journal> <ledger>` on a real or test journal and confirm: Transaction ID column is present and
  first (column A), values are `00001-001` format, and that a re-run on the same output produces
  identical IDs (idempotent).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Start immediately — no dependencies
- **Phase 3 (US1+US2)**: Starts after T001 (modifies the same feature file). Tests T003–T008 can
  begin in parallel once T001 is done. Implementation T009–T013 begins after RED checkpoint.
- **Phase 4 (US3)**: Starts after Phase 3 GREEN checkpoint. T015 adds to `test_transaction_id.py`
  (created in T004) — T004 must be complete.
- **Phase 5 (Polish)**: Depends on all story phases complete

### Within Phase 3

1. T001 (Setup): sequential — modifies feature file and steps file
2. T003 (BDD), T004 (unit), T005 (e2e): start after T001 — different files, can parallel
3. T006 (BDD US2): modifies same feature+steps files as T003 — run after T003
4. T007 (engine unit), T008 (e2e): different files from T006 — parallel with T006
5. **Checkpoint**: confirm RED before T009
6. T009 (constants), T010 (assigner), T011 (engine), T012 (mode): sequential where they share
   files (T009 before T010 before T011 since T011 imports from T009 and T010)
7. T013 (steps sort key): independent of T009–T012
8. **Checkpoint**: confirm GREEN

### Within Phase 4

1. T014 (BDD): modifies feature+steps files (different from T004's unit file) — start of phase
2. T015 (unit): adds to test_transaction_id.py — independent of T014
3. T016 (e2e): adds to e2e file — independent of T014 and T015
4. T014, T015, T016: can be written in parallel (different files)
5. **Checkpoint**: confirm RED
6. T020 (assigner re-run logic): depends on T015's tests defining expected behaviour
7. T021 (mode prior-ledger read): independent of T020 (different file, both needed)
8. **Checkpoint**: confirm GREEN

### Parallel Opportunities

- T004, T005: parallel (different files from T003)
- T007, T008: parallel (different files from T006)
- T009, T013: parallel (different files)
- T010: after T009 (imports constants)
- T011: after T010 (imports TransactionIDAssigner)
- T015, T016: parallel with T014 (different files)
- T020, T021: parallel (different files)
- T022, T023, T024: parallel (independent quality tool runs)

---

## Parallel Example: Phase 3 (US1 + US2 Tests)

```powershell
# Step 1 — After T001 completes:
# Launch in parallel (different files):
#   T004: create tests/unit/create_ledger/test_transaction_id.py
#   T005: add e2e US1 tests to tests/integration/test_create_ledger_e2e.py

# Step 2 — After T003 completes:
# Launch in parallel (different files):
#   T007: add TestTransactionIDSort to tests/unit/create_ledger/test_engine.py
#   T008: add e2e US2 test to tests/integration/test_create_ledger_e2e.py

# Step 3 — RED confirmed. Implementation (sequential on shared files):
#   T009 → T010 → T011 → T012
# In parallel with T009–T012:
#   T013 (steps sort key — different file)
```

## Parallel Example: Phase 4 (US3 Tests)

```powershell
# Write RED tests in parallel (different files):
#   T014: feature scenarios + steps bindings
#   T015: TestReRunAssignment in test_transaction_id.py
#   T016: e2e re-run tests in test_create_ledger_e2e.py

# Confirm RED, then implement in parallel:
#   T020: TransactionIDAssigner re-run logic (transaction_id.py)
#   T021: mode.py prior-ledger read (_load_prior_ids helper + wire into execute)
```

---

## Implementation Strategy

### MVP First (US1 + US2 — Phase 3 Only)

1. Phase 1: T001, T002
2. Phase 3 tests: T003–T008 (write, confirm RED)
3. Phase 3 implementation: T009–T013 (implement, confirm GREEN)
4. **STOP and validate**: `python -m pytest tests/ -v` — all GREEN
5. Shippable: every ledger now has Transaction IDs; same-date offsets are unambiguous

### Full Delivery

1. Phase 1 → Phase 3 (MVP) → Phase 4 (US3) → Phase 5 (Polish)
2. Each phase produces a working, independently testable increment

---

## Notes

- **LEDGER_COLUMNS shift**: Adding `Transaction ID` at index 0 shifts all existing column indices
  by +1. The `LEDGER_COLUMNS.index(col_name) + 1` formula in `mode.py` self-corrects — no
  manual offset change required.
- **Sort key change**: The engine sort changes from `(account, sub_account, date)` to
  `(date, account, sub_account, reference)`. Existing tests that use named columns
  (`out_df["Account Value"]`) are unaffected. Tests using `.iloc[N]` indices are safe because
  the test data has unique accounts/sub_accounts or single-position journals.
- **T020 assigner algorithm**: The key insight is distinguishing "new row before all prior rows",
  "new row between prior rows", and "new row after all prior rows". Walk the sorted df once,
  tracking the last-seen prior-ID row to determine which prefix block to assign the new suffix to.
- **Date normalization in T021**: Prior ledger dates may be `datetime64` when read from XLSX.
  Normalize with `str(pd.Timestamp(val).date())` → `"YYYY-MM-DD"` before building the key tuple.
- **T010 prior_ids default**: Engine's `prior_ids` parameter should default to `None` (not `{}`
  mutable default) to avoid Python mutable-default-argument anti-pattern. Use `None` with
  `prior_ids or {}` inside the body.
- **[P] tasks** = truly different files or genuinely independent in-memory operations
- Confirm RED before GREEN — never skip the failure verification step
