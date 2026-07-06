# Tasks: Fix Cash Offset Signs

**Input**: Design documents from `specs/006-fix-cash-offset-signs/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Tests are MANDATORY per the project constitution. Every user story MUST include `pytest`
unit tests (`tests/unit/`) AND BDD Gherkin scenarios (`tests/features/`). Tests MUST be written and
confirmed failing BEFORE implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (truly different files or independent operations with no shared state)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task

---

## Phase 1: Setup (No New Infrastructure Required)

**Purpose**: This feature has no new infrastructure. The one setup task is a semantic correction
to an existing test that is currently passing with wrong-signed data — fixing it before touching
production code ensures the test suite stays honest throughout.

- [x] T001 Correct `test_invariant_holds_for_trading_offset` Cash row value from `1000.0` to
  `-1000.0` in `tests/unit/create_ledger/test_engine.py` (line ~319) — semantic fix, test still
  passes, ensures test data matches HL sign convention before main work begins

---

## Phase 2: Foundational (No Blocking Prerequisites)

**Purpose**: There are no shared foundational components that block user stories — the formula
fix (US1/US2) and the journal store extension (US3) are independent. Phase 2 is intentionally
empty; proceed directly to user story phases.

---

## Phase 3: User Stories 1 & 2 — Buy/Sell Offset Sign Correction (Priority: P1) 🎯 MVP

**Goal**: Fix `_make_offset` so buy offsets carry a negative value (cash outflow) and sell offsets
carry a positive value (cash inflow). Update all test fixtures and CSV test data that asserted the
old inverted signs. US1 and US2 share the same one-line formula fix and the same set of test
fixture corrections, so they are grouped in a single phase.

**Independent Test**:
```powershell
python -m pytest tests/unit/consolidate_journals/test_offset_generator.py -v
```
All tests must be GREEN after T008. Zero tests may assert the old inverted signs.

### Tests for US1 + US2 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T008)

- [x] T002 [US1] In `tests/unit/consolidate_journals/test_offset_generator.py`: change `_buy`
  default `value` from `"1000.00"` to `"-1000.00"` (line 15) — HL buys are negative; test will
  now FAIL because current code negates to `+1000` but assertion expects `-1000`

- [x] T003 [US2] In `tests/unit/consolidate_journals/test_offset_generator.py`: change `_sell`
  default `value` from `"-75.00"` to `"75.00"` (line 32) — HL sells are positive; test will now
  FAIL because current code negates to `-75` but assertion expects `+75`

- [x] T004 [US1] In `TestGenerateFromDf._df_with_buy` (line 153): change `"value": 1000.0`
  to `"value": -1000.0` — DataFrame fixture now reflects correct HL sign; `test_buy_df_offset_value_negated`
  will FAIL

- [x] T005 [US2] In `TestGenerateFromDf._df_with_sell` (line 169): change `"value": -75.0`
  to `"value": 75.0` — DataFrame fixture now reflects correct HL sign; `test_sell_df_offset_value_positive`
  will FAIL

- [x] T006 [US1] Rename test `test_buy_offset_value_is_negated` → `test_buy_offset_value_mirrors_trade`
  and `test_buy_offset_quantity_equals_negated_value` → `test_buy_offset_quantity_mirrors_trade_value`
  in `tests/unit/consolidate_journals/test_offset_generator.py` (lines 76, 80) — names now describe
  correct semantics

- [x] T007 [US2] Rename test `test_sell_produces_offset_with_positive_value` →
  `test_sell_offset_value_mirrors_trade` and `test_sell_offset_quantity_equals_negated_sell_value` →
  `test_sell_offset_quantity_mirrors_trade_value` in `tests/unit/consolidate_journals/test_offset_generator.py`
  (lines 93, 98) — names now describe correct semantics

**Checkpoint**: Run the full `test_offset_generator.py` suite — T002–T005 changes must cause at
least 4 tests to FAIL. Do NOT proceed to T008 until failures are confirmed.

### Implementation for US1 + US2

- [x] T008 [US1][US2] In `src/modes/consolidate_journals/offset_generator.py` `_make_offset`
  (lines 49–50): change `value=-event.value` → `value=event.value` and `quantity=-event.value` →
  `quantity=event.value` — one-line fix satisfying FR-001 (buy mirrors trade, negative) and
  FR-002 (sell mirrors trade, positive)

**Checkpoint**: All `test_offset_generator.py` tests must now be GREEN. Confirm before continuing.

### CSV Test Data Correction (US1 + US2)

- [x] T009 [P] [US1][US2] In `tests/data/consolidate_journals/valid_hl_simple.csv` (lines 2–4):
  change buy B12345 value `2000.00` → `-2000.00`, sell S67890 value `-75.00` → `75.00`,
  buy B11111 value `2500.00` → `-2500.00` — all three changes in one edit; reflects HL sign
  convention (buys negative, sells positive)

**Checkpoint**: Run BDD feature tests — `python -m pytest tests/features/ -v -k consolidate` —
confirm all consolidate_journals scenarios still pass with corrected CSV values.

---

## Phase 4: User Story 3 — Journal Store Update-In-Place for Stale Offsets (Priority: P2)

**Goal**: Add `rectify_offsets()` to `JournalStore` so that re-running `consolidate_journals`
against a journal already containing wrong-sign offsets (produced by the buggy feature 004)
automatically corrects them. Update `ConsolidationEngine.run()` to call `rectify_offsets()`.

**Independent Test**:
```powershell
python -m pytest tests/unit/consolidate_journals/test_journal_store.py -v -k rectify
python -m pytest tests/features/ -v -k "stale"
```
All rectify unit tests and the new BDD scenario must be GREEN after T018.

### Tests for US3 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T018)

- [x] T010 [US3] Update `tests/features/consolidate_journals.feature`: add Gherkin scenario
  *"Given a consolidated journal contains a buy offset with the wrong sign, When consolidate_journals
  is re-run, Then the buy offset value is updated to match the trade value"* — scenario fails until
  T018+T019 are complete (FR-005, SC-004); add matching step definition in
  `tests/features/steps/consolidate_journals_steps.py`

- [x] T011 [US3] In `tests/unit/consolidate_journals/test_journal_store.py`: add class
  `TestRectifyOffsets` with test `test_rectify_offsets_corrects_wrong_sign_buy` — build a
  `JournalStore` containing a buy row (value=−1000) and its existing offset row with wrong sign
  (value=+1000); call `store.rectify_offsets()`; assert return value is `1` and the offset row's
  value is now `-1000.0`

- [x] T012 [US3] In `tests/unit/consolidate_journals/test_journal_store.py` `TestRectifyOffsets`:
  add `test_rectify_offsets_corrects_wrong_sign_sell` — build a store containing a sell row
  (value=+500) and its existing offset with wrong sign (value=−500); assert `rectify_offsets()`
  returns `1` and the offset value is now `+500.0`

- [x] T013 [P] [US3] In `tests/unit/consolidate_journals/test_journal_store.py` `TestRectifyOffsets`:
  add `test_rectify_offsets_no_change_when_correct` — build a store where the offset value already
  matches the trade value; assert `rectify_offsets()` returns `0` and the offset row is unchanged

- [x] T014 [P] [US3] In `tests/unit/consolidate_journals/test_journal_store.py` `TestRectifyOffsets`:
  add `test_rectify_offsets_does_not_touch_non_offset_rows` — build a store with mixed rows
  (deposit, buy, income, offset); call `rectify_offsets()`; assert only the offset row is modified,
  all other rows unchanged

**Checkpoint**: Run `python -m pytest tests/unit/consolidate_journals/test_journal_store.py -v -k rectify`
— all four unit tests must FAIL with `AttributeError: 'JournalStore' object has no attribute 'rectify_offsets'`.
Run `python -m pytest tests/features/ -v -k stale` — BDD scenario must FAIL too.

### Implementation for US3

- [x] T015 [US3] In `src/modes/consolidate_journals/journal_store.py`: add method
  `rectify_offsets(self) -> int` — iterates over `self._df` buy/sell rows; for each, computes the
  expected offset reference (`ref + OFFSET_SUFFIX`); finds any existing offset row with that
  reference; if found and `offset_value != trade_value`: updates `value` and `quantity` in place
  to match `trade_value`; logs corrected count at INFO level; returns total count corrected.
  Note: no `trades` parameter — the method reads from `self._df` directly, keeping encapsulation

- [x] T016 [US3] In `src/modes/consolidate_journals/consolidator.py` `ConsolidationEngine.run()`
  (after the initial `store.save(journal_path)` call and before the `missing_offset_trades` block):
  call `store.rectify_offsets()`; if the return count > 0, save the journal and log a structured
  INFO entry with `{"rectified_offsets": count}`

**Checkpoint**: All four `TestRectifyOffsets` unit tests and the BDD stale-offset scenario must be
GREEN. Re-run the full consolidate_journals test suite — confirm no regressions.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates and end-to-end validation.

- [x] T017 [P] Run `mypy --strict src/ pipeline.py` — zero errors (Constitution gate III); fix
  any type annotation issues introduced by `rectify_offsets` (return type `int`, no parameters)

- [x] T018 [P] Run `ruff check .` — zero violations (Constitution gate IV)

- [x] T019 [P] Run `ruff format --check .` — zero violations; auto-fix with `ruff format .` if
  needed

- [x] T020 Add integration test to `tests/integration/test_create_ledger_e2e.py` verifying SC-003:
  given a journal with a deposit (+2000), a buy offset (−1000), and a sell offset (+300) on the
  Cash sub-account, running `create_ledger` produces a final Cash `Account Value` of exactly
  `+1300.00` (satisfies SC-003: Cash = deposit + sell proceeds − buy costs)

- [x] T021 Run full test suite `python -m pytest tests/ -v` — zero failures across all 3 test
  directories (features/, unit/, integration/); confirms T020 passes and no regressions

- [x] T022 Validate quickstart.md scenarios manually: re-run `consolidate_journals` on
  `HL_SIPP_Journal.xlsx` and confirm buy offset values are negative and sell offset values are
  positive per `quickstart.md` assertions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 3 (US1/US2)**: Starts after T001 — independent of Phase 4
- **Phase 4 (US3)**: Starts after Phase 3 checkpoint — `rectify_offsets` test fixtures reuse the
  corrected sign convention established in Phase 3
- **Phase 5 (Polish)**: Depends on all story phases complete; T020 depends on Phase 3 (formula
  fix must be in place before integration test can pass)

### Within Phase 3 (US1/US2)

1. T002–T007: Write and rename tests (sequential edits within the same file — do not attempt
   concurrent edits to `test_offset_generator.py`)
2. **Confirm failures** before T008
3. T008: One-line formula fix
4. **Confirm GREEN** before T009
5. T009: CSV corrections (single edit covering all 3 lines)

### Within Phase 4 (US3)

1. T010: BDD Gherkin scenario (new `.feature` scenario + step)
2. T011–T014: Unit tests (T013 and T014 are parallel — different test methods in same class)
3. **Confirm failures** (AttributeError + BDD failure) before T015
4. T015: `rectify_offsets` implementation (no parameter — reads from self._df)
5. T016: Wire into `ConsolidationEngine.run()`

### Parallel Opportunities

- T013, T014: Parallel (independent test methods within `TestRectifyOffsets`)
- T017, T018, T019: Parallel (independent quality tool runs)

---

## Parallel Example: Phase 3 (US1 + US2)

```bash
# Step 1 — RED: Sequential edits to test_offset_generator.py (single file, one pass):
# T002: _buy value "1000.00" → "-1000.00"
# T003: _sell value "-75.00" → "75.00"
# T004: _df_with_buy value 1000.0 → -1000.0
# T005: _df_with_sell value -75.0 → 75.0
# T006: rename buy test names
# T007: rename sell test names
# Confirm ≥4 tests FAIL

# Step 2 — GREEN: Fix formula (offset_generator.py T008)
# Confirm all tests PASS

# Step 3 — CSV: Single edit covering all 3 value corrections (T009)
# Confirm BDD feature tests still PASS
```

## Parallel Example: Phase 4 (US3)

```bash
# Step 1 — RED:
#   T010: BDD scenario (consolidate_journals.feature + steps)
#   T011: TestRectifyOffsets.test_rectify_corrects_wrong_sign_buy
#   T012: TestRectifyOffsets.test_rectify_corrects_wrong_sign_sell
#   T013, T014: parallel — independent test methods
# Confirm AttributeError on all four unit tests + BDD failure

# Step 2 — GREEN:
#   T015: implement rectify_offsets(self) -> int
#   T016: wire into consolidator (no argument: store.rectify_offsets())
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only — Phase 3)

1. Complete Phase 1 (T001)
2. Complete Phase 3 (T002–T009) — one-line fix + fixture + CSV corrections
3. **STOP and validate**: `python -m pytest tests/unit/consolidate_journals/test_offset_generator.py -v`
4. Shippable: buy/sell offset signs are correct for all new runs; stale-offset self-healing (US3) deferred

### Full Delivery

1. Phase 1 → Phase 3 (MVP) → Phase 4 (US3) → Phase 5 (Polish)
2. Each phase produces a working, independently testable increment

---

## Notes

- **Assertion values are unchanged** in test_offset_generator.py: corrected fixture (buy=−1000)
  + corrected formula (mirror, not negate) = same assertion value (−1000). The code path changes;
  the expected output does not.
- **T004–T007 [P] removed**: all four edit `test_offset_generator.py`. Apply as one sequential
  pass — do not attempt concurrent edits to the same file.
- **T009 consolidated**: the three CSV line corrections (originally T009/T010/T011) are merged
  into one task since they always apply together to the same file.
- **rectify_offsets has no parameter**: the method reads from `self._df` internally. The
  consolidator calls `store.rectify_offsets()` with no arguments, preserving encapsulation.
- **T015 implementation note**: `self._df[self._df["action"].isin(["buy", "sell"])]` to get
  trade rows; for each, look up `ref + OFFSET_SUFFIX` in `self._df["reference"]`; update
  in-place via `self._df.loc[offset_mask, "value"] = trade_value` and `"quantity"` likewise.
- [P] tasks = truly different files or genuinely independent in-memory operations
- [Story] label maps each task to its user story for traceability
- Confirm RED before GREEN — never skip the failure verification step
