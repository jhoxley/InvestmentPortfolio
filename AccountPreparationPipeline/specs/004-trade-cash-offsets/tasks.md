# Tasks: Trade Cash Offset Entries

**Input**: Design documents from `specs/004-trade-cash-offsets/`
**Prerequisites**: plan.md âœ… | spec.md âœ… | research.md âœ… | data-model.md âœ… | contracts/ âœ…

**Tests**: MANDATORY per constitution. BDD Gherkin scenarios (`tests/features/`) and `pytest`
unit tests (`tests/unit/`) are required. Tests MUST be written and confirmed failing (Red)
BEFORE implementation begins (Green). Red-Green-Refactor strictly observed.

**Organization**: Three user stories. US1 and US2 share implementation (dedup is baked into
the backfill architecture); US3 is test-only. All story phases include tests-first ordering.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[US1/2/3]**: Maps to User Story 1, 2, or 3 from spec.md
- All implementation paths are under `src/modes/consolidate_journals/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the new enum value and named constants that every subsequent task depends on.
No new package or directory is created â€” all changes are within the existing module.

- [x] T001 Add `TRADING = "trading"` to `ActionType` StrEnum in `src/modes/consolidate_journals/schema.py` (add after `WITHDRAWAL = "withdrawal"` with a comment: `# Synthetic cash offset for buy/sell trades`)
- [x] T002 [P] Add `OFFSET_SUFFIX: str = "-offset"` and `RE_OFFSET: re.Pattern[str] = re.compile(r"^[BS]\d+-offset$")` to `src/modes/consolidate_journals/constants.py` (after the `RE_SELL` constant)

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Extend the deduplication logic so offset references are classified as
"transaction references" (deduped by `date + reference`). Without this, two trades on the same
date with identical values would have their offsets incorrectly deduplicated.

**âš ï¸ CRITICAL**: No user story implementation can begin until this phase is complete.

- [x] T003 Extend `_is_transaction_reference()` in `src/modes/consolidate_journals/journal_store.py`: add `RE_OFFSET` to the imports from `constants.py` and extend the function body to `return bool(RE_BUY.match(reference) or RE_SELL.match(reference) or RE_OFFSET.match(reference))`

**Checkpoint**: Constants importable, dedup logic updated â€” US1 implementation can now begin.

---

## Phase 3: User Story 1 â€” Cash Offsets Generated for Buy and Sell Trades (Priority: P1) ðŸŽ¯ MVP

**Goal**: After every `consolidate_journals` run the journal contains exactly one synthetic
Cash offset row (`sub_account = "Cash"`, `action = "trading"`) for every buy/sell trade,
including any pre-existing trades that were present before this feature was deployed.

**Independent Test**: Run `python pipeline.py consolidate_journals <journal> <frags_dir> HL
"ISA"` against a directory containing one buy (B12345, Â£1000.00) and one sell (S67890,
-Â£75.00). Open the output XLSX and verify two offset rows exist with the correct reference,
value, quantity, and sub_account. Run a second time and confirm no new rows are added.

### Tests for User Story 1 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before T007â€“T010)

- [x] T004 [P] [US1] Write unit tests for `OffsetGenerator` in `tests/unit/consolidate_journals/test_offset_generator.py` â€” confirm FAILING (ImportError expected): buy row produces offset with `sub_account = "Cash"`, `action = "trading"`, `reference = "<ref>-offset"`, `value = -trade.value`, `quantity = -trade.value`; sell row produces offset with negated sell value (i.e. positive, since HL stores sell proceeds as negative); deposit/income/fee/withdrawal produce no offset; empty input returns empty list; `generate_from_df()` produces same results as `generate()` for equivalent DataFrame rows

- [x] T005 [P] [US1] Add BDD scenarios to `tests/features/consolidate_journals.feature` and skeleton step bindings in `tests/features/steps/consolidate_journals_steps.py`: Scenario "Offset rows are generated for buy and sell trades" (Given/When/Then with subprocess call asserting offset row count equals buy+sell row count); Scenario "No offset rows generated for deposit-only input" (Given deposit-only CSV, Then zero trading rows in journal); Scenario "Existing journal receives backfilled offsets on first post-deployment run" (Given a journal already containing a buy trade but no offset row, When consolidate_journals is run with no new fragments, Then the offset row is inserted)

- [x] T006 [P] [US1] Write integration test class `TestUSOffsets` in `tests/integration/test_consolidate_journals_e2e.py` with methods: `test_buy_generates_offset_row` (programmatic journal + buy CSV â†’ assert offset exists with correct fields); `test_sell_generates_offset_row` (sell CSV â†’ assert offset with positive value for negative-value sell); `test_deposit_generates_no_offset` (deposit-only CSV â†’ assert zero trading rows); `test_backfill_existing_trade` (pre-populate journal with a buy row, run consolidate_journals with empty frags dir, assert offset is backfilled)

### Implementation for User Story 1

- [x] T007 [US1] Create `src/modes/consolidate_journals/offset_generator.py`: implement `OffsetGenerator` class with `generate(events: list[JournalEvent]) -> list[JournalEvent]` (filters to BUY/SELL, constructs JournalEvent per trade with sub_account=CASH_SUB_ACCOUNT, action=ActionType.TRADING, reference=event.reference+OFFSET_SUFFIX, value=-event.value, quantity=-event.value) and `generate_from_df(trades: pd.DataFrame) -> list[JournalEvent]` (converts DataFrame rows to JournalEvent objects then delegates to `generate()`); import `ActionType`, `JournalEvent` from `schema.py`; import `CASH_SUB_ACCOUNT`, `OFFSET_SUFFIX` from `constants.py` â€” run T004 to confirm Green

- [x] T008 [US1] Add `missing_offset_trades(self) -> pd.DataFrame` method to `JournalStore` in `src/modes/consolidate_journals/journal_store.py`: return empty DataFrame if `self._df` is empty; build set of existing offset references from rows where `action == ActionType.TRADING.value`; return copy of rows where action is `"buy"` or `"sell"` AND `(reference + OFFSET_SUFFIX)` is NOT in the offset-ref set â€” run T004 to confirm relevant tests Green

- [x] T009 [US1] Update `ConsolidationEngine.run()` in `src/modes/consolidate_journals/consolidator.py`: after `store.save(journal_path)`, add backfill block â€” call `store.missing_offset_trades()`, if non-empty generate offsets via `OffsetGenerator().generate_from_df(missing)`, call `store.merge(offsets)` accumulating `total_inserted`, call `store.save(journal_path)` again, log `"Offset backfill complete"` at INFO with `offsets_generated` count â€” run T005 and T006 to confirm Green

- [x] T010 [US1] Complete BDD step implementations in `tests/features/steps/consolidate_journals_steps.py` for all new US1 scenarios: `@given` steps create programmatic XLSXs via `pd.DataFrame.to_excel` in `tmp_path`; `@then` steps read output journal with `pd.read_excel`, filter by `action == "trading"`, assert row count and field values â€” run T005 to confirm Green

**Checkpoint**: US1 fully functional â€” verify with a real journal XLSX and HL CSV directory before proceeding.

---

## Phase 4: User Story 2 â€” Offset Deduplication on Re-Run (Priority: P2)

**Goal**: Running `consolidate_journals` twice with identical inputs produces a journal with
the same row count both times â€” no offset row is duplicated.

**Independent Test**: Run the mode twice against the same input. Assert the journal row count
after the second run equals the row count after the first run. Assert `events_inserted` in the
second run's summary is 0.

**Note**: No new implementation tasks â€” deduplication is already ensured by T003
(`_is_transaction_reference` extended for RE_OFFSET) and T008 (`missing_offset_trades` checks
for existing offsets before backfilling). This phase is tests-only.

### Tests for User Story 2 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before US1 is complete)

- [x] T011 [P] [US2] Add BDD scenarios to `tests/features/consolidate_journals.feature`: Scenario "Re-running with same inputs does not duplicate offset rows" (run twice, assert row count unchanged); Scenario "Incremental run adds offsets only for new trades" (first run with 2 buys, second run with 1 new buy, assert exactly 1 new offset added)

- [x] T012 [P] [US2] Add step implementations for US2 scenarios in `tests/features/steps/consolidate_journals_steps.py`: `@given "I have already run consolidate_journals once with offset support"` sets up initial journal state; `@then` steps assert journal row count and `events_inserted` summary count

- [x] T013 [US2] Add integration test methods to `TestUSOffsets` in `tests/integration/test_consolidate_journals_e2e.py`: `test_rerun_does_not_duplicate_offsets` (run twice, assert row count unchanged); `test_incremental_run_adds_only_new_offsets` (two buys on first run, one new buy on second run, assert journal has 6 rows: 3 trades + 3 offsets, not 7)

**Checkpoint**: US2 confirmed â€” idempotency verified.

---

## Phase 5: User Story 3 â€” Offset Rows Visible in Consolidation Summary (Priority: P3)

**Goal**: The `Events inserted` count in the success summary includes both real trade events
and synthetic offset rows so the user can verify offsets were generated without inspecting
the XLSX manually.

**Independent Test**: Run `consolidate_journals` against a file with two buy events and one
sell event. Confirm the summary output on stdout contains `Events inserted:  6` (3 real + 3
offsets).

**Note**: No new implementation tasks â€” offsets go through `store.merge()` which already
increments `total_inserted`. This phase is tests-only.

### Tests for User Story 3 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before US1 is complete)

- [x] T014 [P] [US3] Add BDD scenario to `tests/features/consolidate_journals.feature`: Scenario "Events inserted count includes offset rows" (Given 2 buy + 1 sell events, When consolidate_journals runs, Then stdout contains "Events inserted:  6")

- [x] T015 [P] [US3] Add step implementation in `tests/features/steps/consolidate_journals_steps.py`: `@then "the stdout summary shows {count:d} events inserted including offsets"` checks result.stdout for the `Events inserted:  {count}` line

- [x] T016 [US3] Add integration test method `test_summary_includes_offset_count` to `TestUSOffsets` in `tests/integration/test_consolidate_journals_e2e.py`: programmatic XLSX with 2 buy + 1 sell; run via subprocess; assert stdout contains `"Events inserted:  6"`

**Checkpoint**: US3 confirmed â€” all three user stories complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates per constitution.

- [x] T017 [P] Run `mypy --strict src/` â€” zero errors required (Constitution gate III); verify `offset_generator.py` and updated `journal_store.py` methods are fully type-annotated including `pd.DataFrame` return types
- [x] T018 [P] Run `ruff check .` and `ruff format --check .` â€” zero violations required (Constitution gate IV)
- [x] T019 Verify structured logging in `consolidator.py`: backfill block emits INFO log with `offsets_generated` count; no new `print()` statements (Constitution gate VI)
- [x] T020 Run full test suite `pytest tests/` â€” all unit, BDD, and integration tests pass including pre-existing `consolidate_journals` tests; confirm all four constitution quality gates green before marking feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” T001 and T002 can start immediately in parallel
- **Foundational (Phase 2)**: Depends on Phase 1; T003 after T001 and T002
- **US1 (Phase 3)**: Depends on Phase 2; T004â€“T006 in parallel (write tests); T007â€“T010 sequential (implement then verify)
- **US2 (Phase 4)**: Depends on Phase 3 completion; T011â€“T012 in parallel; T013 sequential
- **US3 (Phase 5)**: Depends on Phase 3 completion; T014â€“T015 in parallel; T016 sequential
- **Polish (Phase 6)**: Depends on Phases 3â€“5; T017 and T018 in parallel; T019 then T020 sequential

### Within User Story 1

1. Write tests T004â€“T006 in parallel â€” confirm all FAIL (ImportError or missing `OffsetGenerator`)
2. Implement in dependency order: `offset_generator.py` (T007) â†’ `missing_offset_trades` (T008) â†’ backfill in engine (T009)
3. Complete BDD steps (T010) last â€” run T005 to confirm Green
4. Run all T006 integration tests to confirm Green

### US2 and US3 dependency on US1

- US2 and US3 tests can be written (T011â€“T016) any time after the Foundational phase
- They will fail until US1 (T007â€“T010) is complete
- No separate implementation tasks are needed â€” the backfill architecture satisfies both stories

---

## Parallel Opportunities

### Phase 1 (Setup)

```
T001 âˆ¥ T002
```

### Phase 3 Tests (write all in parallel)

```
(T004 âˆ¥ T005 âˆ¥ T006) â†’ T007 â†’ T008 â†’ T009 â†’ T010
```

### Phases 4 & 5 Tests (can write in parallel with US1 implementation)

```
(T011 âˆ¥ T012 âˆ¥ T013) âˆ¥ (T014 âˆ¥ T015 âˆ¥ T016)   (all blocked only until US1 ships)
```

### Phase 6 (Polish â€” gates in parallel)

```
(T017 âˆ¥ T018) â†’ T019 â†’ T020
```

---

## Implementation Strategy

### MVP (Complete Feature â€” single story)

1. Phase 1: Setup (T001â€“T002)
2. Phase 2: Foundational (T003)
3. Phase 3 tests (T004â€“T006) â€” confirm Red
4. Phase 3 implementation (T007â€“T010) â€” confirm Green
5. **STOP and VALIDATE**: run `python pipeline.py consolidate_journals <real_journal.xlsx> <frags/> HL "ISA"` and inspect the output XLSX â€” verify offset rows are present and correct
6. Phase 4: US2 tests (T011â€“T013) â€” confirm Green (no new code needed)
7. Phase 5: US3 tests (T014â€“T016) â€” confirm Green (no new code needed)
8. Phase 6: Polish (T017â€“T020)

---

## Notes

- `[P]` tasks touch different files with no incomplete dependencies â€” safe to run in parallel
- US2 and US3 have NO implementation tasks â€” the backfill architecture built for US1 satisfies both
- `OffsetGenerator` has no I/O â€” it is fully testable without the filesystem or pipeline framework
- `missing_offset_trades()` is the key idempotency mechanism: if all offsets exist, it returns an empty DataFrame and no extra write occurs
- `generate_from_df()` converts DataFrame rows to `JournalEvent` objects; both methods share a private helper to avoid duplication
- The HL CSV stores sell proceeds as **negative values** (confirmed from test data) â€” so `-sell.value` correctly yields a positive offset (cash inflow). No special sign handling is needed.
