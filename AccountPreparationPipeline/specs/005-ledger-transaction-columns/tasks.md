---

description: "Task list for feature 005: Ledger Transaction Columns"
---

# Tasks: Ledger Transaction Columns

**Input**: Design documents from `/specs/005-ledger-transaction-columns/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Tests are MANDATORY per the project constitution. Every user story MUST include Gherkin
BDD feature files (`tests/features/`) and `pytest` unit tests (`tests/unit/`). Tests MUST be
written and confirmed failing BEFORE implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project structure required — all changes are within existing files.

*(No setup tasks — this feature enhances existing source files only.)*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the new column-name constants that all subsequent code and tests depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T001 Add `LEDGER_COL_ACCOUNT_VALUE`, `LEDGER_COL_ACCOUNT_QUANTITY`, `LEDGER_COL_TRANSACTION_VALUE`, `LEDGER_COL_TRANSACTION_QUANTITY`, and `LEDGER_COLUMNS` constants to `src/modes/create_ledger/constants.py`

**Checkpoint**: Constants available — user story work can now begin in parallel.

---

## Phase 3: User Story 1 — Transaction Columns for Lineage (Priority: P1) 🎯 MVP

**Goal**: Extend `LedgerEngine` to output nine columns. `Transaction Value` and `Transaction Quantity`
capture the per-row sign-adjusted delta, enabling per-event lineage tracing through each position.

**Independent Test**: Run `create_ledger` against a two-buy journal; verify output has 9 columns,
`Transaction Value` on row 2 equals `−500.0`, and `Account Value` on row 2 equals `−1500.0`.

### Tests for User Story 1 ⚠️ (MANDATORY — write FIRST, confirm they FAIL before T005)

- [x] T002 [P] [US1] Add BDD scenarios for Transaction Value/Quantity to `tests/features/create_ledger.feature`: single buy (Transaction Value equals Account Value), two sequential buys (Transaction Value = row delta), buy-then-sell (Transaction Value reflects sell's contribution), two positions independent, nine-column schema assertion
- [x] T003 [P] [US1] Add `TestTransactionColumns` class to `tests/unit/create_ledger/test_engine.py`: assert `Transaction Value` equals the per-row adj_value for buy, sell, and cash rows; assert first row of each group has `Transaction Value == Account Value`; assert `Transaction Quantity` mirrors the same pattern
- [x] T004 [P] [US1] Add BDD step implementations for new Transaction scenarios in `tests/features/steps/create_ledger_steps.py`: steps that read `Transaction Value`/`Transaction Quantity` from the output XLSX and assert expected values; step for nine-column schema check via `list(df.columns) == LEDGER_COLUMNS`

### Implementation for User Story 1

- [x] T005 [US1] Update `LedgerEngine.run()` in `src/modes/create_ledger/engine.py`: assign `df[LEDGER_COL_ACCOUNT_VALUE]` from cumsum of `adj_value`; assign `df[LEDGER_COL_ACCOUNT_QUANTITY]` from cumsum of `adj_quantity`; assign `df[LEDGER_COL_TRANSACTION_VALUE] = df["adj_value"]`; assign `df[LEDGER_COL_TRANSACTION_QUANTITY] = df["adj_quantity"]`; drop `"value"`, `"quantity"`, `"adj_value"`, `"adj_quantity"`; update empty-input early return to `pd.DataFrame(columns=LEDGER_COLUMNS)`; return `df[LEDGER_COLUMNS]`
- [x] T006 [US1] Update `CreateLedgerMode.execute()` in `src/modes/create_ledger/mode.py`: replace the two separate `JOURNAL_COLUMNS.index(...)` column-index lookups with a single loop over `[(LEDGER_COL_ACCOUNT_VALUE, NUMBER_FORMAT_VALUE), (LEDGER_COL_TRANSACTION_VALUE, NUMBER_FORMAT_VALUE), (LEDGER_COL_ACCOUNT_QUANTITY, NUMBER_FORMAT_QUANTITY), (LEDGER_COL_TRANSACTION_QUANTITY, NUMBER_FORMAT_QUANTITY)]` using `LEDGER_COLUMNS.index(col_name) + 1`; add imports of `LEDGER_COLUMNS`, `LEDGER_COL_ACCOUNT_VALUE`, `LEDGER_COL_ACCOUNT_QUANTITY`, `LEDGER_COL_TRANSACTION_VALUE`, `LEDGER_COL_TRANSACTION_QUANTITY` from `src.modes.create_ledger.constants`; remove unused `JOURNAL_COLUMNS` import from `src.modes.consolidate_journals.constants`; **remove the `print(f"{COMPLETION_MSG}: ...")` statement on mode.py:80** — the `_logger.info(COMPLETION_MSG, extra={...})` call already records the same information with full structured context; `print()` is prohibited by Constitution VI

**Checkpoint**: Nine-column ledger output produced. Run `pytest tests/unit/create_ledger/test_engine.py::TestTransactionColumns -v` to verify US1 tests pass.

---

## Phase 4: User Story 2 — Invariant Holds Across All Event Types (Priority: P2)

**Goal**: Add comprehensive invariant tests proving `Account Value[i] = Account Value[i−1] + Transaction Value[i]`
holds for every row and every event type, programmatically.

**Independent Test**: Run `pytest tests/unit/create_ledger/test_engine.py::TestInvariant -v` and
`pytest tests/integration/test_create_ledger_e2e.py::TestCreateLedgerE2E::test_invariant_holds_for_all_rows -v` — both must pass after T005.

### Tests for User Story 2 ⚠️ (MANDATORY — write after T001; verify they FAIL before T005 is complete)

- [x] T007 [P] [US2] Add `TestInvariant` class to `tests/unit/create_ledger/test_engine.py`: for a multi-row, multi-position DataFrame loop all rows per `(account, sub_account)` group and assert `Account Value[i] − Account Value[i−1] == Transaction Value[i]` (treat `Account Value[i−1] = 0` for first row of each group); cover buy, sell, cash deposit, and trading-offset action types; assert same invariant holds for `Account Quantity` / `Transaction Quantity`
- [x] T008 [P] [US2] Add `test_invariant_holds_for_all_rows` to `tests/integration/test_create_ledger_e2e.py`: build a journal containing buy, sell, deposit, and trading-offset rows across two positions; run pipeline; read output XLSX; group by `(account, sub_account)` and programmatically assert the value invariant and quantity invariant hold for every row in every group

*(No implementation tasks — the invariant is guaranteed by the `adj_value` retention in T005)*

**Checkpoint**: Both invariant tests pass. Confirms SC-001 and SC-002 from the spec.

---

## Phase 5: User Story 3 — Column Renames Backward-Compatible (Priority: P3)

**Goal**: Update all existing tests that reference the old `value` and `quantity` column names to use
`Account Value` and `Account Quantity`. After T005, these tests will fail — this phase repairs them.

**Independent Test**: Full suite `pytest tests/ -v` passes with zero failures.

### Tests for User Story 3 ⚠️ (MANDATORY — perform after T005 when existing tests are broken)

- [x] T009 [P] [US3] Update existing `Then` step text in `tests/features/create_ledger.feature`: replace all references to "output row value", "output row quantity", "Cash row value", "Cash row quantity" with "Account Value" / "Account Quantity" to match the renamed columns
- [x] T010 [P] [US3] Update all column name references in `tests/features/steps/create_ledger_steps.py`: `df.iloc[x]["value"]` → `df.iloc[x]["Account Value"]`, `df.iloc[x]["quantity"]` → `df.iloc[x]["Account Quantity"]` throughout all `@then` step functions; replace the local `JOURNAL_COLUMNS` list constant with an import of `LEDGER_COLUMNS` from `src.modes.create_ledger.constants`
- [x] T011 [P] [US3] Update all column name references in `tests/unit/create_ledger/test_engine.py`: `["value"]` → `["Account Value"]`, `["quantity"]` → `["Account Quantity"]` throughout all existing test methods in `TestBuyEvents`, `TestSellEvents`, `TestCashRows`, `TestPositionIsolation`; update `TestRowCountAndSchema.test_output_columns_match_journal_columns` to assert `list(result.columns) == LEDGER_COLUMNS` and add `LEDGER_COLUMNS` import from `src.modes.create_ledger.constants`; **keep the `JOURNAL_COLUMNS` import from `consolidate_journals.constants`** — it is still required by the `_make_df()` helper (line 11) to construct 7-column input DataFrames; only its use in the output assertion is replaced
- [x] T012 [P] [US3] Update all column name references in `tests/integration/test_create_ledger_e2e.py`: `["value"]` → `["Account Value"]`, `["quantity"]` → `["Account Quantity"]` throughout all test methods in `TestCreateLedgerE2E`; add `assert not output_path.exists()` to `test_missing_input_returns_exit_code_2` to verify FR-012's requirement that no output file is created on invalid input

*(No source code changes — US3 is test repair only)*

**Checkpoint**: All existing tests updated. Full suite green. Confirms SC-003 and SC-004 from the spec.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates per the project constitution.

- [x] T013 [P] Run `mypy --strict src/ pipeline.py` — zero errors required (Constitution gate)
- [x] T014 [P] Run `ruff check .` and `ruff format --check .` — zero violations required (Constitution gate)
- [x] T015 Run full test suite `python -m pytest tests/ -v` and confirm zero failures across all unit, BDD, and integration tests
- [x] T016 Run quickstart.md validation: execute pipeline against a real journal, open XLSX, manually verify nine columns present in defined order and that a sample row satisfies `Account Value[i] − Account Value[i−1] == Transaction Value[i]`; also verify number formatting on all four numeric columns (`Account Value`, `Transaction Value` as `#,##0.00`; `Account Quantity`, `Transaction Quantity` as `#,##0.######`) — this is the only verification of FR-010 since `pd.read_excel()` strips cell formats and no automated test covers it
- [x] T017 Verify SC-005 baseline: run `create_ledger` against a 500-row journal and confirm completion in under 10 seconds — inherited O(N) complexity from feature 003; this is a manual regression check to guard against accidental quadratic behaviour introduced by the new column assignments

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Requires T001. Tests T002–T004 written after T001; T005–T006 are the implementation tasks.
- **US2 (Phase 4)**: Requires T001. Tests T007–T008 written after T001 (should fail until T005 completes). No implementation tasks.
- **US3 (Phase 5)**: Requires T005 complete. Existing tests will break after the engine change; T009–T012 repair them.
- **Polish (Phase 6)**: Requires all user story phases complete.

### User Story Dependencies

- **US1 (P1)**: Depends on T001 only — core implementation gate
- **US2 (P2)**: Tests written after T001; pass automatically once T005 is done
- **US3 (P3)**: Depends on T005 — old tests break on schema change, this phase fixes them

### Within Each User Story

- Tests for each story written and confirmed failing before the implementation task (T005)
- T005 is the single critical implementation task — flips new tests green and breaks old ones
- T006 depends on T005 (uses LEDGER_COLUMNS to index columns)
- T009–T012 (US3) are parallel with each other; each touches a separate file

### Parallel Opportunities

- T002, T003, T004 — parallel (three different test files)
- T007, T008 — parallel (test_engine.py, test_create_ledger_e2e.py)
- T009, T010, T011, T012 — parallel (four different files)
- T013, T014 — parallel (independent quality checks)

---

## Parallel Example: User Story 1

```bash
# RED phase — write failing tests in parallel:
Task: "T002 — Add BDD scenarios to tests/features/create_ledger.feature"
Task: "T003 — Add TestTransactionColumns to tests/unit/create_ledger/test_engine.py"
Task: "T004 — Add BDD steps to tests/features/steps/create_ledger_steps.py"

# GREEN phase — implement:
Task: "T005 — Update engine.py (makes T002–T004 and T007–T008 green; breaks old tests)"
Task: "T006 — Update mode.py (depends on T005)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2 (T001) — constants defined
2. Write US1 tests T002–T004 — confirm they fail
3. Implement T005–T006 — confirm US1 tests pass
4. **STOP and VALIDATE**: Nine-column output verified, Transaction Value/Quantity correct
5. Continue with US2 (T007–T008) then US3 (T009–T012)

### Incremental Delivery

1. T001 → Constants defined
2. T002–T004, T007–T008 → All new tests written (RED)
3. T005 → Engine change (US1+US2 tests GREEN; old tests broken)
4. T006 → Mode updated (number formatting correct)
5. T009–T012 → Existing tests repaired (all GREEN)
6. T013–T016 → Quality gates all pass

---

## Notes

- [P] tasks = different files, no dependencies on each other
- T005 is the pivotal task — it changes the engine output schema, makes new tests pass, and breaks existing column-name references
- After T005: T002–T004, T007–T008 pass; T011–T012 fail (old column refs break) → fixed by T009–T012
- Run `pytest tests/ -v` after each phase checkpoint to track progress
- Quality gates (T013–T014) require zero violations — run early to catch type errors before final phase
- T006 includes removing the `print()` from mode.py (Constitution VI violation — no print in production code); the `_logger.info` already present handles structured output
- T011 retains the `JOURNAL_COLUMNS` import — it is needed by `_make_df()` for test input construction; only the output assertion switches to `LEDGER_COLUMNS`
- T016 is the sole FR-010 verification (number format); T017 is the sole SC-005 verification (performance baseline)
