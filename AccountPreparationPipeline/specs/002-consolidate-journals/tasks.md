# Tasks: Journal Fragment Consolidation

**Input**: Design documents from `specs/002-consolidate-journals/`
**Prerequisites**: plan.md âœ… | spec.md âœ… | research.md âœ… | data-model.md âœ… | contracts/ âœ…

**Tests**: MANDATORY per constitution. BDD Gherkin scenarios (`tests/features/`) and `pytest`
unit tests (`tests/unit/`) are required for every user story. Tests MUST be written and confirmed
failing (Red) BEFORE implementation begins (Green). Red-Green-Refactor strictly observed.

**Organization**: Tasks grouped by user story for independent implementation and delivery.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- All implementation paths are under `src/modes/consolidate_journals/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies, create directory scaffolding, and author all test fixture
data before any story work begins.

- [x] T001 Add `pandas>=2.0,<3.0` and `openpyxl>=3.1,<4.0` to `requirements.txt`
- [x] T002 [P] Create `src/modes/consolidate_journals/` package skeleton: `__init__.py` and `parsers/__init__.py` (empty files to establish import paths)
- [x] T003 [P] Create `tests/unit/consolidate_journals/` and `tests/unit/consolidate_journals/parsers/` package skeletons with `__init__.py` files
- [x] T004 [P] Author five test CSV fixtures in `tests/data/consolidate_journals/`: `valid_hl_simple.csv` (3 rows, no preamble), `valid_hl_with_preamble.csv` (3 rows with metadata preamble before header), `valid_hl_contrib.csv` (Deposit + BACS rows), `invalid_no_header.csv` (no recognisable header row), `invalid_bad_value.csv` (one row with non-numeric value, one valid row)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and protocols shared by all three user stories. Must complete
before any story implementation begins.

**âš ï¸ CRITICAL**: No user story implementation can begin until this phase is complete.

- [x] T005 Create `src/modes/consolidate_journals/constants.py`: `JOURNAL_COLUMNS` (ordered list of 7 column names), `DEDUP_KEY_COLUMNS` (`["date", "reference"]`), `DEDUP_FALLBACK_KEY_COLUMNS` (`["date", "action", "value"]`), `RE_BUY` and `RE_SELL` (compiled regex `^B\d+$` / `^S\d+$`), `HL_HEADER_COL0 = "Trade date"`, `HL_HEADER_COL1 = "Settle date"`, `HL_CONTRIB_ACTIONS = frozenset({"Deposit", "BACS"})`, summary label constants
- [x] T006 [P] Create `src/modes/consolidate_journals/parsers/base.py`: `FragmentParser` Protocol with `parse(file_path: Path, account: str) -> ParseResult` method signature; runtime-checkable
- [x] T007 [P] Write unit tests in `tests/unit/consolidate_journals/test_schema.py`: `ActionType` enum values and string representations, `JournalEvent` frozen dataclass field types, `ParseError` `line_number` optional, `ParseResult` always has both lists, `ConsolidationSummary` counts non-negative â€” confirm tests FAIL (ImportError expected) before T008
- [x] T008 Create `src/modes/consolidate_journals/schema.py`: `ActionType(str, Enum)` with BUY/SELL/CONTRIB/WITHDRAWAL, `JournalEvent` frozen dataclass, `ParseError` frozen dataclass, `ParseResult` frozen dataclass, `ConsolidationSummary` frozen dataclass â€” run T007 tests to confirm they now pass

**Checkpoint**: Core types importable and tested â€” user story implementation can now begin.

---

## Phase 3: User Story 1 â€” First-Time Consolidation from HL Exports (Priority: P1) ðŸŽ¯ MVP

**Goal**: Parse a directory of HL CSV exports and write a new consolidated journal XLSX with all
events correctly normalised. This is the foundational delivery path.

**Independent Test**: Run `python pipeline.py consolidate_journals out.xlsx tests/data/consolidate_journals/ HL "Test ISA"` with a non-existent `out.xlsx` â€” verify the file is created, has the correct 7 columns, contains all parseable rows, and the process exits 0.

### Tests for User Story 1 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementing T014â€“T019)

- [x] T009 [P] [US1] Write BDD Gherkin acceptance scenarios for US1 in `tests/features/consolidate_journals.feature` (Feature: Journal Fragment Consolidation; Scenarios: creates new journal from valid HL CSVs, skips preamble rows, maps B-reference to buy, maps S-reference to sell, maps Deposit/BACS to contrib, strips description suffix) â€” and write `tests/features/steps/consolidate_journals_steps.py` step skeleton (functions with `pass`; wired to subprocess call)
- [x] T010 [P] [US1] Write unit tests for `HLFragmentParser` in `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: header discovery (finds header after preamble rows), B-reference â†’ `ActionType.BUY`, S-reference â†’ `ActionType.SELL`, description with suffix â†’ sub-account with suffix stripped, description without suffix â†’ unchanged, settle date parsed correctly â€” confirm FAILING (ImportError expected)
- [x] T011 [P] [US1] Write unit tests for `JournalStore` in `tests/unit/consolidate_journals/test_journal_store.py` (load/save only at this stage): `load()` on non-existent path returns store with empty DataFrame; `save()` creates XLSX with columns matching `JOURNAL_COLUMNS` in correct order â€” confirm FAILING
- [x] T012 [P] [US1] Write unit tests for `ConsolidationEngine` in `tests/unit/consolidate_journals/test_consolidator.py`: run with `valid_hl_simple.csv` using mocked `FragmentParser` â†’ `ConsolidationSummary.events_inserted` equals event count, `errors` is empty, `files_processed` equals 1 â€” confirm FAILING
- [x] T013 [P] [US1] Write unit tests for `ConsolidateJournalsMode` in `tests/unit/consolidate_journals/test_mode.py`: `register_arguments()` declares 4 positional args (`journal_path`, `fragments_dir`, `method`, `account`); unrecognised method value â†’ `execute()` returns exit code 2; valid args with mocked engine â†’ returns exit code 0 â€” confirm FAILING

### Implementation for User Story 1

- [x] T014 [US1] Implement `HLFragmentParser` in `src/modes/consolidate_journals/parsers/hl.py`: open CSV with `csv.reader`, scan for header row matching `HL_HEADER_COL0`/`HL_HEADER_COL1`, map column indices, iterate data rows, apply action mapping via `RE_BUY`/`RE_SELL`/`HL_CONTRIB_ACTIONS`, strip description suffix (find and remove `@ ...` suffix and preceding quantity token), parse `Decimal` value and quantity, collect `JournalEvent` instances, return `ParseResult` â€” run T010 tests to confirm they pass
- [x] T015 [US1] Implement `JournalStore` in `src/modes/consolidate_journals/journal_store.py`: `load(path: Path) -> JournalStore` reads XLSX with `pandas.read_excel(engine="openpyxl")` if file exists, else creates empty DataFrame with `JOURNAL_COLUMNS`; `save(path: Path) -> None` writes via `DataFrame.to_excel(engine="openpyxl", index=False)` using atomic temp-file + rename â€” run T011 tests to confirm they pass
- [x] T016 [US1] Implement `ConsolidationEngine` in `src/modes/consolidate_journals/consolidator.py`: `run(journal_path, fragments_dir, method, account) -> ConsolidationSummary` â€” call `JournalStore.load()`, resolve `FragmentParser` via `_get_parser(method)` factory, iterate files in `fragments_dir` (HL: `*.csv` only), call `parser.parse()` for each, call `store.merge()` (stub returning `(len(events), 0)` until T023), accumulate errors, call `store.save()`, return `ConsolidationSummary` â€” run T012 tests to confirm they pass
- [x] T017 [US1] Implement `ConsolidateJournalsMode` in `src/modes/consolidate_journals/mode.py`: `name = "consolidate_journals"`, `description = "Merge journal fragment files into a standardised consolidated journal XLSX"`, `register_arguments()` adds 4 positional args with full `help=` strings, `execute()` validates `fragments_dir` exists and `method` is valid enum â†’ exit code 2 if not, calls `engine.run()`, calls `render_summary()`, returns exit code 0 â€” run T013 tests to confirm they pass
- [x] T018 [US1] Register `ConsolidateJournalsMode` in `pipeline.py`: add import and `registry.register(ConsolidateJournalsMode())` alongside `ExampleMode`
- [x] T019 [US1] Write and run integration test for US1 in `tests/integration/test_consolidate_journals_e2e.py`: subprocess `python pipeline.py consolidate_journals <tmp_xlsx> tests/data/consolidate_journals/ HL "Test ISA"` â†’ assert exit code 0, assert output XLSX exists, assert `pandas.read_excel()` yields rows with correct column names and `account == "Test ISA"`

**Checkpoint**: US1 fully functional â€” new journal can be created from HL CSV exports. Demo-ready.

---

## Phase 4: User Story 2 â€” Incremental Update of an Existing Journal (Priority: P2)

**Goal**: When a consolidated journal already exists, running the mode again merges only new events
and skips any events already present (idempotent operation).

**Independent Test**: Create a journal from `valid_hl_simple.csv`. Run again with the same CSV.
Assert `events_inserted == 0` and `events_merged == 3` (all rows recognised as duplicates).

### Tests for User Story 2 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementing T023)

- [x] T020 [P] [US2] Add BDD scenarios for US2 to `tests/features/consolidate_journals.feature`: "incremental update adds new events", "re-running with same inputs inserts zero events", "mix of new and existing events â€” only new events inserted"; add matching step implementations to `tests/features/steps/consolidate_journals_steps.py`
- [x] T021 [P] [US2] Write unit tests for `JournalStore.merge()` in `tests/unit/consolidate_journals/test_journal_store.py`: new events â†’ all inserted (inserted=N, merged=0), duplicate events (same date+reference) â†’ all skipped (inserted=0, merged=N), mix of new and duplicate â†’ correct split counts, cash/deposit row uses fallback key (date+action+value) â€” confirm FAILING for `merge()` method
- [x] T022 [US2] Write integration test for US2 in `tests/integration/test_consolidate_journals_e2e.py`: run once to create journal, run again with same dir â†’ assert second run summary shows `events_inserted=0, events_merged=N`; run with new CSV dir â†’ assert new events appear and pre-existing rows are unchanged

### Implementation for User Story 2

- [x] T023 [US2] Implement `JournalStore.merge()` in `src/modes/consolidate_journals/journal_store.py`: convert `list[JournalEvent]` to DataFrame, compute dedup key column (primary: date+reference when reference matches `RE_BUY`/`RE_SELL` pattern; fallback: date+action+value), left-join against existing store on key, separate into `to_insert` (anti-join) and `duplicate` (matched) sets, append `to_insert` to internal DataFrame, return `(len(to_insert), len(duplicate))` â€” run T021 tests to confirm they pass

**Checkpoint**: US1 + US2 both independently testable. Running twice is safe (idempotent).

---

## Phase 5: User Story 3 â€” Graceful Error Handling with Mixed File Quality (Priority: P3)

**Goal**: When some fragment files are malformed or unrecognisable, the pipeline processes all
remaining valid files, writes their events to the journal, and produces a clear error report
identifying every failing file (and line, where applicable).

**Independent Test**: Run with `invalid_no_header.csv` and `valid_hl_simple.csv` in the same
directory â†’ assert exit code 0, assert valid events are in the output XLSX, assert stdout error
section names `invalid_no_header.csv` with appropriate message.

### Tests for User Story 3 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementing T028â€“T030)

- [x] T024 [P] [US3] Add BDD scenarios for US3 to `tests/features/consolidate_journals.feature`: "valid file processes despite co-located invalid file", "no-header file reported in error section", "bad-value row reported with line number â€” surrounding valid rows still processed"; add step implementations to `tests/features/steps/consolidate_journals_steps.py`
- [x] T025 [P] [US3] Write unit tests for `HLFragmentParser` error paths in `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: no-header file â†’ `ParseResult(events=[], errors=[ParseError(line_number=None)])`, row with non-numeric value â†’ `ParseError` with correct `line_number`, valid rows before and after bad row still present in `events` list â€” confirm FAILING
- [x] T026 [P] [US3] Write unit tests for `ConsolidationEngine` error propagation in `tests/unit/consolidate_journals/test_consolidator.py`: mixed valid + invalid files â†’ `ConsolidationSummary.errors` contains errors from invalid file, `events_inserted` counts only events from valid files, engine does not abort when one file fails â€” confirm FAILING
- [x] T027 [P] [US3] Write unit tests for `render_summary()` in `tests/unit/consolidate_journals/test_mode.py`: summary with zero errors renders `"ERRORS\n  None"`, summary with errors renders `"ERRORS (N total)"` followed by one line per error with file name and line number (if present) â€” confirm FAILING

### Implementation for User Story 3

- [x] T028 [US3] Harden `HLFragmentParser` error handling in `src/modes/consolidate_journals/parsers/hl.py`: wrap each row iteration in try/except, catch date parse failures, value parse failures, empty sub-account, and unknown action pattern â†’ `ParseError` with `line_number` from `csv.reader.line_num`; ensure the `ParseResult` always contains all successfully parsed rows even when errors exist; never let any exception propagate â€” run T025 tests to confirm they pass
- [x] T029 [US3] Implement `render_summary(summary: ConsolidationSummary) -> str` as a standalone pure function in `src/modes/consolidate_journals/mode.py` (independently testable): produces the two-section stdout block per `contracts/cli-contract.md`; integrate into `ConsolidateJournalsMode.execute()` â€” run T027 tests to confirm they pass
- [x] T030 [US3] Add integration test for US3 in `tests/integration/test_consolidate_journals_e2e.py`: run with mixed valid + invalid directory â†’ assert exit code 0, assert stdout contains "ERRORS" section with `invalid_no_header.csv` named, assert output XLSX contains only events from valid files

**Checkpoint**: All three user stories independently functional. Partial success (valid files processed despite errors) confirmed.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates, structured logging verification, and BDD step completeness.

- [x] T031 [P] Verify structured logging coverage in `src/modes/consolidate_journals/`: mode entry (correlation ID + mode name), per-file parse start/end (file path), per-error WARNING records (file + line + detail), consolidation summary INFO record (all ConsolidationSummary fields), mode exit â€” add any missing log statements (Constitution gate VI)
- [x] T032 [P] Run `mypy --strict src/` â€” resolve all type errors to zero (Constitution gate III); add `types-openpyxl` or `pandas-stubs` to `requirements-dev.txt` if needed
- [x] T033 [P] Run `ruff check .` and `ruff format --check .` â€” resolve all violations to zero (Constitution gate IV)
- [x] T034 Run full test suite `pytest tests/` â€” all unit, BDD, and integration tests pass; confirm all four constitution quality gates green before marking feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” can start immediately; T002, T003, T004 can run in parallel after T001
- **Foundational (Phase 2)**: Depends on Phase 1; T006, T007 parallel after T005; T008 waits on T007 passing
- **US1 (Phase 3)**: Depends on Phase 2 completion; T009â€“T013 parallel (write tests); T014â€“T019 sequential (implement then register)
- **US2 (Phase 4)**: Depends on Phase 3 completion; T020â€“T022 parallel (write tests); T023 implements
- **US3 (Phase 5)**: Depends on Phase 4 completion; T024â€“T027 parallel (write tests); T028â€“T030 sequential (implement then test)
- **Polish (Phase 6)**: Depends on Phase 5 completion; T031, T032, T033 parallel; T034 depends on all three

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational (Phase 2). No dependency on US2 or US3.
- **US2 (P2)**: Starts after US1 is complete. `JournalStore.merge()` extends the store built for US1.
- **US3 (P3)**: Starts after US2 is complete. Adds error-path handling to the parser + engine + mode built for US1.

### Within Each User Story

1. Test tasks (T00x marked `[USN]`) â€” write ALL tests first
2. Confirm tests fail (ImportError or AssertionError â€” either is acceptable Red state)
3. Implement in dependency order: schema â†’ parser â†’ store â†’ engine â†’ mode â†’ registration
4. Confirm tests pass after each implementation task
5. Integration test last â€” confirms the story from the outside

---

## Parallel Opportunities

### Phase 1 (Setup)

```
T001 â†’ (T002 âˆ¥ T003 âˆ¥ T004)
```

### Phase 2 (Foundational)

```
T005 â†’ (T006 âˆ¥ T007) â†’ T008
```

### Phase 3 Tests (US1 â€” write tests in parallel)

```
(T009 âˆ¥ T010 âˆ¥ T011 âˆ¥ T012 âˆ¥ T013) â†’ T014 â†’ T015 â†’ T016 â†’ T017 â†’ T018 â†’ T019
```

### Phase 4 Tests (US2 â€” write tests in parallel)

```
(T020 âˆ¥ T021 âˆ¥ T022) â†’ T023
```

### Phase 5 Tests (US3 â€” write tests in parallel)

```
(T024 âˆ¥ T025 âˆ¥ T026 âˆ¥ T027) â†’ T028 â†’ T029 â†’ T030
```

### Phase 6 (Polish â€” gates in parallel)

```
(T031 âˆ¥ T032 âˆ¥ T033) â†’ T034
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001â€“T004)
2. Complete Phase 2: Foundational (T005â€“T008) â€” CRITICAL, blocks all stories
3. Write US1 tests (T009â€“T013) â€” confirm Red
4. Implement US1 (T014â€“T019) â€” confirm Green
5. **STOP and VALIDATE**: `python pipeline.py consolidate_journals out.xlsx tests/data/consolidate_journals/ HL "My ISA"` â€” new XLSX created
6. Demo / validate with real HL CSV exports

### Incremental Delivery

1. Phase 1 + 2 â†’ foundation stable
2. Phase 3 (US1) â†’ new journal creation works (**MVP demo point**)
3. Phase 4 (US2) â†’ re-running is safe; existing data protected
4. Phase 5 (US3) â†’ partial-success error reporting complete
5. Phase 6 â†’ all quality gates green; feature shipworthy

---

## Notes

- `[P]` tasks can be executed in parallel â€” they touch different files with no incomplete dependencies
- `[USN]` labels trace each task to its user story for independent delivery tracking
- Always confirm tests are **Red** before beginning the corresponding implementation task
- Commit after each completed task (or logical group) to preserve incremental progress
- The `render_summary()` function is kept pure (no side effects) for independent testability
- `JournalStore.save()` uses atomic write (temp file + `Path.rename()`) â€” do not simplify to direct write
- `HLFragmentParser` must never raise â€” all failures encoded as `ParseError`
