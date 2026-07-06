# Tasks: Ledger Running Balance

**Input**: Design documents from `specs/003-create-ledger/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

**Tests**: MANDATORY per constitution. BDD Gherkin scenarios (`tests/features/`) and `pytest`
unit tests (`tests/unit/`) are required. Tests MUST be written and confirmed failing (Red)
BEFORE implementation begins (Green). Red-Green-Refactor strictly observed.

**Organization**: Single user story — all implementation tasks belong to US1.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[US1]**: Maps to User Story 1 — Generate a Position Ledger from a Consolidated Journal
- All implementation paths are under `src/modes/create_ledger/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create package scaffolding. No new dependencies — pandas and openpyxl are already
declared in `requirements.txt`.

- [x] T001 Create `src/modes/create_ledger/` package: `__init__.py` (empty file to establish import path)
- [x] T002 [P] Create `tests/unit/create_ledger/` package: `__init__.py` (empty file)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Named constants shared by both `engine.py` and `mode.py`. Must exist before either
can be implemented.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [x] T003 Create `src/modes/create_ledger/constants.py`: `CASH_SUB_ACCOUNT: str = "Cash"`, `BUY_SELL_ACTIONS: frozenset[str] = frozenset({"buy", "sell"})`, `SELL_ACTION: str = "sell"`, `LOG_CL_CORRELATION_ID: str = "correlation_id"`, `COMPLETION_MSG: str = "Ledger written"`

**Checkpoint**: Constants importable — US1 implementation can now begin.

---

## Phase 3: User Story 1 — Generate a Position Ledger from a Consolidated Journal (Priority: P1) 🎯 MVP

**Goal**: Read a consolidated journal XLSX, compute cumulative running value and quantity per
(account, sub_account) position using sign-adjustment rules, and write the result as a
seven-column ledger XLSX with numeric formatting.

**Independent Test**: Run `python pipeline.py create_ledger <input.xlsx> <output.xlsx>` where the
input contains buy, sell, deposit, and Cash events across two positions. Assert exit code 0;
assert output has the same row count as input; assert the cumulative value and quantity in the
final row of each position match hand-calculated expected totals.

### Tests for User Story 1 ⚠️ (MANDATORY — write FIRST, ensure they FAIL before implementing T007–T011)

- [x] T004 [P] [US1] Write BDD Gherkin scenarios in `tests/features/create_ledger.feature`: Feature: Ledger Running Balance; Scenarios — "buy events produce negated cumulative value and positive cumulative quantity", "sell events produce negated cumulative value and negated cumulative quantity", "Cash rows with blank quantity use value as quantity for cumulation", "running totals are independent per position (account + sub_account)", "output row count equals input row count", "action and reference columns are unchanged in output" — and write step skeleton in `tests/features/steps/create_ledger_steps.py` (functions wired to subprocess call; fixtures create input XLSX programmatically in `tmp_path`)
- [x] T005 [P] [US1] Write unit tests for `LedgerEngine` in `tests/unit/create_ledger/test_engine.py` — confirm FAILING (ImportError expected): buy row value negated then cumulated (e.g. buy £1000 → adj_value = -1000 → cumsum = -1000); sell row value negated and quantity negated (e.g. sell 50 units → adj_quantity = -50); two sequential buys cumulate correctly (buy £500 + buy £300 → cumsum values = -500, -800); Cash row with NaN quantity copies value before cumulation; two positions in same DataFrame accumulate independently; output has same number of rows as input; columns `date`, `account`, `sub_account`, `action`, `reference` are unchanged; output column order matches `JOURNAL_COLUMNS`
- [x] T006 [P] [US1] Write unit tests for `CreateLedgerMode` in `tests/unit/create_ledger/test_mode.py` — confirm FAILING: `name == "create_ledger"`; `description` is non-empty; `register_arguments()` declares exactly 2 positional args (`input_path`, `output_path`); missing input file → `execute()` returns exit code 2; input with missing columns → `execute()` returns exit code 2; valid input → `execute()` returns exit code 0

### Implementation for User Story 1

- [x] T007 [US1] Implement `LedgerEngine` in `src/modes/create_ledger/engine.py`: `run(input_df: pd.DataFrame) -> pd.DataFrame` method; import `JOURNAL_COLUMNS` from `src.modes.consolidate_journals.constants`; validate all `JOURNAL_COLUMNS` columns present — raise `ValueError` if any missing; apply Cash rule: `df.loc[(df["sub_account"] == CASH_SUB_ACCOUNT) & df["quantity"].isna(), "quantity"] = df["value"]`; compute `adj_value` (`-value` where action in `BUY_SELL_ACTIONS`, else `value`); compute `adj_quantity` (`-quantity` where action == `SELL_ACTION`, else `quantity`); stable sort by `(account, sub_account, date)`; `value = groupby(["account", "sub_account"])["adj_value"].cumsum()`; `quantity = groupby(["account", "sub_account"])["adj_quantity"].cumsum()`; drop `adj_value` and `adj_quantity`; return DataFrame with `JOURNAL_COLUMNS` column order — run T005 to confirm Green
- [x] T008 [US1] Implement `CreateLedgerMode` in `src/modes/create_ledger/mode.py`: `name = "create_ledger"`, `description = "Compute running position balances from a consolidated journal"`; `register_arguments()` adds `input_path` (metavar `INPUT_PATH`) and `output_path` (metavar `OUTPUT_PATH`) positional args with full `help=` strings; `execute()` validates `input_path` exists → exit code 2 if not; reads XLSX with `pd.read_excel(input_path, engine="openpyxl")`; calls `LedgerEngine().run(df)` in try/except `ValueError` → log error + exit code 2; writes output via `pd.ExcelWriter(output_path, engine="openpyxl")` with `NUMBER_FORMAT_VALUE` applied to `value` column and `NUMBER_FORMAT_QUANTITY` applied to `quantity` column (both imported from `src.modes.consolidate_journals.constants`); prints `f"Ledger written: {len(result)} rows processed → {output_path}"` to stdout; emits structured INFO log record with `correlation_id`, `input_path`, `output_path`, `rows_processed`, `rows_written` — run T006 to confirm Green
- [x] T009 [US1] Register `CreateLedgerMode` in `pipeline.py`: add `from src.modes.create_ledger.mode import CreateLedgerMode` import and `registry.register(CreateLedgerMode())` inside `_build_registry()` alongside existing modes
- [x] T010 [US1] Complete BDD step implementations in `tests/features/steps/create_ledger_steps.py`: `@given` steps create input XLSX programmatically using `pd.DataFrame.to_excel` into `tmp_path`; `@when` step invokes `subprocess.run([sys.executable, str(PIPELINE_PATH), "create_ledger", str(input_path), str(output_path)])` and stores `CompletedProcess` result; `@then` steps assert exit code, read output with `pd.read_excel`, assert row counts, assert cumulative values in final rows, assert unchanged columns
- [x] T011 [US1] Write and run integration test in `tests/integration/test_create_ledger_e2e.py`: programmatically create input XLSX with buy/sell/Cash events in `tmp_path`; invoke `pipeline.py create_ledger <input> <output>` via subprocess; assert exit code 0; assert output XLSX row count equals input; assert known cumulative value and quantity for each position at the last date; assert exit code 2 for non-existent input path; assert `consolidate_journals` mode still listed in pipeline help (regression check)

**Checkpoint**: US1 fully functional — ledger generated from any consolidated journal XLSX.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates per constitution.

- [x] T012 [P] Run `mypy --strict src/` — zero errors required (Constitution gate III); verify `engine.py` and `mode.py` are fully type-annotated including `pd.DataFrame` parameter and return types
- [x] T013 [P] Run `ruff check .` and `ruff format --check .` — zero violations required (Constitution gate IV)
- [x] T014 Verify structured logging in `src/modes/create_ledger/mode.py`: mode entry log (correlation ID + mode name at INFO), computation completion log (rows_processed + rows_written at INFO), error logs for invalid input (at ERROR) — add any missing log statements (Constitution gate VI)
- [x] T015 Run full test suite `pytest tests/` — all unit, BDD, and integration tests pass including pre-existing `consolidate_journals` tests; confirm all four constitution quality gates green before marking feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001 and T002 can start immediately in parallel
- **Foundational (Phase 2)**: Depends on Phase 1; T003 after T001
- **US1 (Phase 3)**: Depends on Phase 2; T004–T006 in parallel (write tests); T007–T011 sequential (implement then register)
- **Polish (Phase 4)**: Depends on Phase 3; T012 and T013 in parallel; T014 then T015 sequential

### Within User Story 1

1. Write tests T004–T006 in parallel — confirm all FAIL (ImportError or AttributeError)
2. Implement in dependency order: constants (T003, already done) → engine (T007) → mode (T008) → register (T009)
3. Complete BDD steps (T010) and integration test (T011) last

---

## Parallel Opportunities

### Phase 1 (Setup)

```
T001 ∥ T002
```

### Phase 3 Tests (write all in parallel)

```
(T004 ∥ T005 ∥ T006) → T007 → T008 → T009 → T010 → T011
```

### Phase 4 (Polish — gates in parallel)

```
(T012 ∥ T013) → T014 → T015
```

---

## Implementation Strategy

### MVP (Complete Feature — single story)

1. Phase 1: Setup (T001–T002)
2. Phase 2: Foundational constants (T003)
3. Phase 3 tests (T004–T006) — confirm Red
4. Phase 3 implementation (T007–T011) — confirm Green
5. **STOP and VALIDATE**: run `python pipeline.py create_ledger <real_journal.xlsx> <ledger.xlsx>` and inspect the output XLSX in Excel
6. Phase 4: Polish (T012–T015) — all gates green

---

## Notes

- `[P]` tasks touch different files with no incomplete dependencies — safe to run in parallel
- `LedgerEngine.run()` receives a `pd.DataFrame` and returns a `pd.DataFrame` — it has no I/O concerns; all file handling is in `mode.py`
- Import `JOURNAL_COLUMNS`, `NUMBER_FORMAT_VALUE`, and `NUMBER_FORMAT_QUANTITY` from `src.modes.consolidate_journals.constants` — do not redefine them in `create_ledger`
- No binary test fixture files needed — all input XLSXs are created programmatically in `tmp_path`
- The Cash blank-quantity rule (FR-006) applies BEFORE sign adjustment — set `quantity = value` first, then compute `adj_quantity`
