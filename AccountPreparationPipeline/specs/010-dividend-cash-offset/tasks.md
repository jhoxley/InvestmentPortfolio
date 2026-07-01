# Tasks: Dividend Cash Offset Entries

**Input**: Design documents from `specs/010-dividend-cash-offset/`
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

**Purpose**: Confirm starting state before changes begin

- [X] T001 Run `python -m pytest tests/` to confirm existing baseline (321 tests, 0 failures) before making any changes

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Fix deduplication key selection for all `-offset` references — required before US1, US2,
and US3 can work correctly. Without this fix, `"ST DIV-offset"` uses the fallback dedup key
`(date + action + value)` instead of the correct `(date + reference)`, risking incorrect
deduplication when two dividend offsets share the same date and value.

**⚠️ CRITICAL**: US1, US2, and US3 all depend on this phase being complete first.

- [X] T002 In `src/modes/consolidate_journals/journal_store.py`: replace `RE_OFFSET.match(reference)` in `_is_transaction_reference()` with `reference.endswith(OFFSET_SUFFIX)`, then remove `RE_OFFSET` from the import block at the top of the file. In `src/modes/consolidate_journals/constants.py`: delete the `RE_OFFSET` constant declaration (the line `RE_OFFSET: re.Pattern[str] = re.compile(...)`). Run `ruff check .` to confirm no unused-import violation remains.

**Checkpoint**: `_is_transaction_reference("ST DIV-offset")` now returns True; `RE_OFFSET` is removed. Existing buy/sell offset behaviour is unchanged.

---

## Phase 3: User Story 1 — Dividend Event Generates Same-Sign Cash Offset (Priority: P1) 🎯 MVP

**Goal**: Every `dividend` event in the journal generates a synthetic `trading` row in the Cash
sub-account with the same `value` and `quantity` (positive, matching the dividend).

**Independent Test**: Run `consolidate_journals` with `tests/data/consolidate_journals/valid_hl_st_div.csv`
(existing fixture). The output journal must contain at least one row with `action = "trading"`,
`reference = "ST DIV-offset"`, `sub_account = "Cash"`, and `value` matching the ST DIV value.

### Tests for User Story 1 ⚠️ (write FIRST — confirm they FAIL before implementing)

- [X] T003 [P] [US1] In `tests/unit/consolidate_journals/test_offset_generator.py`: add class `TestOffsetGeneratorDividend` with tests: (a) `test_generate_returns_offset_for_dividend_event` — single DIVIDEND event with value=64.71 → one offset with sub_account="Cash", action=ActionType.TRADING, reference="ST DIV-offset", value=Decimal("64.71"), quantity=Decimal("64.71"); also assert explicitly `offset.value > 0` and `offset.quantity > 0` to satisfy SC-002; (b) `test_generate_skips_non_offset_actions` — events with ActionType.DEPOSIT, INCOME, FEE, WITHDRAWAL, and TRADING actions → generate() returns empty list for all five (covers FR-005 exhaustively); (c) `test_generate_returns_offset_for_all_dividend_reference_types` — one event each for ST DIV, OVR CR, UTC CR, UTO CR, LOYALTYU, LOYALTYC actions → six offsets returned.

- [X] T004 [P] [US1] In `tests/unit/consolidate_journals/test_journal_store.py`: add class `TestMissingOffsetTradesDividend` with tests: (a) `test_missing_offset_trades_returns_dividend_rows_without_offset` — store has one DIVIDEND row with no matching "ST DIV-offset" trading row → `missing_offset_trades()` returns that row; (b) `test_missing_offset_trades_excludes_dividend_with_existing_offset` — store has DIVIDEND row AND corresponding "ST DIV-offset" trading row → `missing_offset_trades()` returns empty DataFrame; (c) `test_missing_offset_trades_returns_mix_of_buy_sell_dividend` — store has BUY, SELL, DIVIDEND each missing their offset → all three returned.

- [X] T005 [P] [US1] In `tests/features/consolidate_journals.feature`: add section `# ─── Feature 010: Dividend Cash Offsets ───` with scenario `Dividend event generates same-sign Cash offset` — Given a valid HL CSV file with ST DIV rows (reusing `valid_hl_st_div.csv` fixture), When I run consolidate_journals, Then exit code is 0 AND the journal contains a row with action "trading" AND reference "ST DIV-offset" AND sub_account "Cash". In `tests/features/steps/consolidate_journals_steps.py`: add the `@scenario` binding and any new step definitions required (reuse existing step definitions where possible — check for overlap with existing "the journal contains N rows with action" step).

### Confirm tests FAIL

- [X] T006 [US1] Run `python -m pytest tests/unit/consolidate_journals/test_offset_generator.py::TestOffsetGeneratorDividend tests/unit/consolidate_journals/test_journal_store.py::TestMissingOffsetTradesDividend -v` and confirm the new tests FAIL (NameError or AssertionError expected — implementation not yet changed). Record failure output for reference.

### Implementation for User Story 1

- [X] T007 [US1] In `src/modes/consolidate_journals/offset_generator.py`: in `OffsetGenerator.generate()`, change the action filter from `e.action in (ActionType.BUY, ActionType.SELL)` to `e.action in (ActionType.BUY, ActionType.SELL, ActionType.DIVIDEND)`. Update the class docstring from "Generate synthetic Cash offset entries for buy/sell trade events." to "Generate synthetic Cash offset entries for buy, sell, and dividend events."

- [X] T008 [US1] In `src/modes/consolidate_journals/journal_store.py`: in `JournalStore.missing_offset_trades()`, change `self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value})` to `self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value, ActionType.DIVIDEND.value})`. Update the method docstring from "Return buy/sell rows that have no corresponding offset row in the journal." to "Return buy, sell, and dividend rows that have no corresponding offset row in the journal."

- [X] T009 [US1] Run `python -m pytest tests/unit/consolidate_journals/test_offset_generator.py tests/unit/consolidate_journals/test_journal_store.py -v` and confirm all US1 tests PASS. Run the full BDD suite `python -m pytest tests/features/ -v` and confirm the new US1 scenario passes.

**Checkpoint**: US1 complete. Dividend events generate Cash offset rows. Existing buy/sell offset tests still pass.

---

## Phase 4: User Story 2 — Income Account Cash Balance is Non-Negative (Priority: P1)

**Goal**: The Cash sub-account `Account Value` is ≥ 0 at every date in the ledger after running
the full pipeline against a real HL Income Account. Validated by extending `rectify_offsets()`
to dividend events for consistent treatment.

**Independent Test**: Run `consolidate_journals` then `create_ledger` against the real HL ISA
Income Account historical files. Filter ledger to Cash sub-account rows. Assert all `Account Value`
entries ≥ 0.

### Tests for User Story 2 ⚠️ (write FIRST — confirm they FAIL before implementing)

- [X] T010 [P] [US2] In `tests/unit/consolidate_journals/test_journal_store.py`: add class `TestRectifyOffsetsDividend` with tests: (a) `test_rectify_offsets_corrects_stale_dividend_offset` — store has DIVIDEND row (value=64.71) with offset row (value=50.00 — stale) → `rectify_offsets()` updates offset value to 64.71 and returns corrected=1; (b) `test_rectify_offsets_skips_correct_dividend_offset` — store has DIVIDEND row and matching offset with same value → `rectify_offsets()` returns corrected=0; (c) `test_rectify_offsets_handles_dividend_alongside_buy_sell` — store has BUY, SELL, DIVIDEND each with stale offsets → all three corrected, returns corrected=3.

- [X] T011 [P] [US2] In `tests/features/consolidate_journals.feature`: add scenario `Income account Cash balance is non-negative after dividend processing` — Given the existing `tests/data/consolidate_journals/valid_hl_mixed_income.csv` fixture (contains ST DIV and INTEREST rows; created in Feature 009), When I run consolidate_journals, Then the journal contains a "Cash" sub_account row with action "trading" AND a positive value, AND no "Cash" trading rows with a negative value. Add step bindings in `tests/features/steps/consolidate_journals_steps.py` as needed. **Note**: this BDD scenario validates the offset-generation half of SC-003 (consolidate_journals only). The create_ledger half of SC-003 (Cash Account Value ≥ 0 in the ledger) is validated manually in T014 against real historical data — it cannot be automated in a unit/BDD fixture without a full pipeline integration harness.

### Confirm tests FAIL

- [X] T012 [US2] Run `python -m pytest tests/unit/consolidate_journals/test_journal_store.py::TestRectifyOffsetsDividend -v` and confirm the new tests FAIL. Record failure output.

### Implementation for User Story 2

- [X] T013 [US2] In `src/modes/consolidate_journals/journal_store.py`: in `JournalStore.rectify_offsets()`, change `self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value})` to `self._df["action"].isin({ActionType.BUY.value, ActionType.SELL.value, ActionType.DIVIDEND.value})`. Update the method docstring to mention dividend events.

- [ ] T014 [US2] Run `python -m pytest tests/unit/consolidate_journals/test_journal_store.py::TestRectifyOffsetsDividend tests/features/ -v` and confirm all US2 tests PASS. Then manually verify SC-003 (create_ledger half) by running the full pipeline against real ISA Income Account data: (1) run `run_pipeline.ps1` (or the equivalent consolidate_journals + create_ledger invocations) targeting the HL ISA Income Account journal at `C:\Users\jhoxl\OneDrive\Investments\Journals\` (use the same account path used in Feature 009 integration testing); (2) open the output ledger XLSX; (3) filter to rows where `sub_account = "Cash"`; (4) confirm every row's `Account Value` column is ≥ 0. Pass criterion: zero rows with a negative Cash `Account Value`.

**Checkpoint**: US2 complete. Cash balance is non-negative across real income account history. All US1 tests still pass.

---

## Phase 5: User Story 3 — Idempotency (Priority: P2)

**Goal**: Re-running `consolidate_journals` with identical inputs produces the same row count —
no dividend offset row is duplicated. This is delivered by the foundational dedup fix (T002)
combined with the `missing_offset_trades()` extension (T008).

**Independent Test**: Run `consolidate_journals` once, record journal row count. Run again with
the same inputs. Journal row count must be unchanged; summary reports 0 events inserted.

### Tests for User Story 3 ⚠️ (write FIRST — confirm pass/fail state before skipping)

- [X] T015 [P] [US3] In `tests/unit/consolidate_journals/test_journal_store.py`: add class `TestDividendOffsetIdempotency` with tests: (a) `test_merge_does_not_duplicate_dividend_offset_on_rerun` — store already contains a "ST DIV-offset" trading row on 2026-03-31; merge() called again with an identical "ST DIV-offset" event → merged_count=1, inserted_count=0, total row count unchanged; (b) `test_is_transaction_reference_returns_true_for_dividend_offset` — `_is_transaction_reference("ST DIV-offset")` returns True; `_is_transaction_reference("OVR CR-offset")` returns True; `_is_transaction_reference("LOYALTYU-offset")` returns True.

- [X] T016 [P] [US3] In `tests/features/consolidate_journals.feature`: add scenario `Re-running consolidate_journals does not duplicate dividend offsets` — Given a journal already containing a ST DIV event and its Cash offset row, When I run consolidate_journals again with the same input CSV, Then the exit code is 0 AND the journal row count is unchanged AND the summary reports 0 events inserted. Add step bindings in `tests/features/steps/consolidate_journals_steps.py` as needed.

### Confirm test state

- [X] T017 [US3] Run `python -m pytest tests/unit/consolidate_journals/test_journal_store.py::TestDividendOffsetIdempotency -v`. These tests may already pass (the foundational dedup fix in T002 is what enables idempotency). If they fail, investigate — `_is_transaction_reference()` should already return True for `-offset` refs after T002. Fix any remaining dedup gap before proceeding.

**Checkpoint**: US3 complete. Re-runs are safe. All US1 and US2 tests still pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates per constitution

- [X] T018 [P] Run `mypy --strict src/` — zero errors required (Constitution gate III). Pay attention to the changed files: `offset_generator.py`, `journal_store.py`, `constants.py`.

- [X] T019 [P] Run `ruff check .` and `ruff format --check .` — zero violations required (Constitution gate IV). The RE_OFFSET removal in T002 should already eliminate the unused-import risk; confirm no new violations.

- [X] T020 Run `python -m pytest tests/ -v` — all tests must pass. New count should be ≥ 321 (baseline) + new tests added in T003, T004, T005, T010, T011, T015, T016. Confirm zero regressions.

- [X] T021 Review structured logging in `consolidator.py` — the "Offset backfill complete" log entry at line ~95 already covers dividend offsets (it logs `offsets_generated` count regardless of action type). Confirm no new log sites are needed. No code change required unless a gap is found.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run immediately
- **Foundational (Phase 2)**: Depends on Phase 1 only — **BLOCKS all user story phases**
- **US1 (Phase 3)**: Depends on Phase 2 complete
- **US2 (Phase 4)**: Depends on Phase 2 complete; can run in parallel with US1 (different methods in journal_store.py)
- **US3 (Phase 5)**: Depends on Phase 2 + Phase 3 complete (uses T008's missing_offset_trades extension)
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Requires foundational dedup fix only
- **US2 (P1)**: Requires foundational dedup fix only; can start in parallel with US1 (different method: rectify_offsets)
- **US3 (P2)**: Requires US1 complete (needs T008's missing_offset_trades extension); foundational dedup fix is what provides the idempotency guarantee

### Within Each User Story

1. Write tests → confirm they FAIL
2. Implement → confirm tests PASS
3. Verify no regressions in full suite

### Parallel Opportunities

- T003, T004, T005 can run in parallel (different test files)
- T010, T011 can run in parallel (different test file sections)
- T015, T016 can run in parallel (different test file sections)
- US1 tests (T003–T005) and US2 tests (T010–T011) can be written in parallel (before any implementation)
- T018 and T019 can run in parallel (mypy and ruff are independent)

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: baseline check
2. Complete Phase 2: dedup fix (prerequisite)
3. Complete Phase 3 (US1): dividend offsets generated
4. Complete Phase 4 (US2): rectify_offsets extended, non-negative balance verified
5. **STOP and VALIDATE**: Run real ISA Income Account through pipeline; verify Cash ≥ 0
6. Skip US3 (idempotency) until US1/US2 are validated

### Full Delivery

Add Phase 5 (US3) after MVP validation — idempotency tests and BDD scenario.

---

## Notes

- **Total tasks**: 21 (T001–T021)
- **US1 tasks**: 7 (T003–T009)
- **US2 tasks**: 5 (T010–T014)
- **US3 tasks**: 3 (T015–T017)
- **Polish tasks**: 4 (T018–T021)
- **[P] tasks** (parallelisable within phase): T003, T004, T005, T010, T011, T015, T016, T018, T019
- All three implementation changes are in existing files — no new source files created
- BDD fixture `tests/data/consolidate_journals/valid_hl_st_div.csv` already exists (Feature 009)
- US3 may require zero implementation tasks — the foundational fix + US1 changes already provide idempotency
