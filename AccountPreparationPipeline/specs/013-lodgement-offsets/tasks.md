---

description: "Task list for Feature 013: Lodgement Deposit and Trade Offsets"
---

# Tasks: Lodgement Deposit and Trade Offsets

**Input**: Design documents from `specs/013-lodgement-offsets/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: Tests are MANDATORY per the project constitution. TDD sequence is strictly:
write tests → confirm they FAIL → implement → confirm they PASS.

**Organization**: Single user story (US1, P1). Tasks grouped into:
Setup → Tests (RED) → Implementation (GREEN) → Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US1]**: Belongs to User Story 1 (the only story)

---

## Phase 1: Setup (Foundational Prerequisite)

**Purpose**: Add the `DEPOSIT_SUFFIX` constant that is imported by both the test tasks and
implementation tasks. This is the only shared prerequisite — all other tasks branch from here.

- [X] T001 Add `DEPOSIT_SUFFIX: str = "-deposit"` to `src/modes/consolidate_journals/constants.py` after the existing `OFFSET_SUFFIX` line

**Checkpoint**: Constant available — test writing and implementation can now proceed.

---

## Phase 2: User Story 1 — Lodgement Companion Generation (Priority: P1) 🎯 MVP

**Goal**: For every lodgement journal entry, generate a deposit companion (`action=deposit`,
`reference={ref}-deposit`, `value=-lodgement.value`) and a trading companion (`action=trading`,
`reference={ref}-offset`, `value=lodgement.value`). Both companions have `quantity=None`.
The behaviour is idempotent (re-running does not duplicate) and backfills historical entries.

**Independent Test**: Process a single-lodgement CSV through the full pipeline. Verify the output
journal contains 3 rows: the lodgement plus 2 companions with correct action, reference, and value.

### Tests for User Story 1 ⚠️ (MANDATORY — write FIRST, confirm FAILING before T007)

- [X] T002 [P] [US1] Write `TestLodgementCompanions` class in `tests/unit/consolidate_journals/test_offset_generator.py` with 16 tests:
  - `test_lodgement_produces_two_companions` — `len(generate([lodgement])) == 2`
  - `test_lodgement_deposit_action` — `any(c.action == ActionType.DEPOSIT for c in companions)`
  - `test_lodgement_deposit_sub_account_is_cash` — deposit companion `sub_account == "Cash"`
  - `test_lodgement_deposit_reference_has_deposit_suffix` — deposit companion `reference == "L003538235-deposit"`
  - `test_lodgement_deposit_value_is_negated` — lodgement -2288.89 → deposit companion value == Decimal("+2288.89")
  - `test_lodgement_deposit_sum_with_lodgement_is_zero` — `lodgement.value + deposit_companion.value == Decimal("0")` (SC-003 invariant)
  - `test_lodgement_deposit_quantity_is_none` — deposit companion `quantity is None`
  - `test_lodgement_trading_action` — `any(c.action == ActionType.TRADING for c in companions)`
  - `test_lodgement_trading_sub_account_is_cash` — trading companion `sub_account == "Cash"`
  - `test_lodgement_trading_reference_has_offset_suffix` — trading companion `reference == "L003538235-offset"`
  - `test_lodgement_trading_value_mirrors_lodgement` — trading companion `value == Decimal("-2288.89")` (same sign as lodgement)
  - `test_lodgement_trading_quantity_is_none` — trading companion `quantity is None`
  - `test_lodgement_date_account_inherited` — both companions inherit `date` and `account`
  - `test_two_lodgements_produce_four_companions` — `len(generate([l1, l2])) == 4`
  - `test_mixed_events_lodgement_and_buy` — buy → 1 offset; lodgement → 2; total 3
  - `test_generate_from_df_lodgement` — `generate_from_df` with lodgement DataFrame produces 2 events

- [X] T003 [P] [US1] Write lodgement dedup and backfill tests in `tests/unit/consolidate_journals/test_journal_store.py` (new test class `TestLodgementDedup`) with 8 tests:
  - `test_lodgement_reference_is_transaction_reference` — `_is_transaction_reference("L003538235") is True`
  - `test_deposit_suffix_reference_is_transaction_reference` — `_is_transaction_reference("L003538235-deposit") is True`
  - `test_lodgement_dedup_uses_primary_key` — re-merging same lodgement event: inserted=1, merged=1
  - `test_two_same_date_same_value_lodgements_both_kept` — two lodgements with identical date+value are both stored (primary key dedup, not fallback)
  - `test_lodgement_missing_both_companions_returned` — lodgement with no companions → returned by `missing_offset_trades()`
  - `test_lodgement_missing_deposit_companion_only` — lodgement with trading companion only → still returned by `missing_offset_trades()`
  - `test_lodgement_missing_trading_companion_only` — lodgement with deposit companion only → still returned by `missing_offset_trades()`
  - `test_lodgement_with_both_companions_not_returned` — lodgement with both companions present → NOT returned by `missing_offset_trades()`

- [X] T004 [P] [US1] Add 3 BDD scenarios to `tests/features/consolidate_journals.feature` under a `# ─── Feature 013: Lodgement Deposit and Trading Companions ───` heading:
  - **Scenario 1** — "Lodgement generates a deposit companion row": Given lodgement CSV + no existing journal, When run consolidate_journals, Then exit code 0 AND journal contains row with `action="deposit"` and `reference="L003538235-deposit"`
  - **Scenario 2** — "Lodgement generates a trading companion row": Same Given/When, Then exit code 0 AND journal contains row with `action="trading"` and `reference="L003538235-offset"`
  - **Scenario 3** — "Re-running consolidation does not duplicate lodgement companions": Given lodgement CSV + no existing journal, When run once AND run again with same inputs, Then exit code 0 AND journal contains exactly 6 rows (2 lodgements + 2 deposit companions + 2 trading companions from `valid_hl_lodgement.csv`)

- [X] T005 [US1] Add step bindings and new step definitions to `tests/features/steps/consolidate_journals_steps.py`:
  - 3 `@scenario` bindings for the Feature 013 scenarios (import from `consolidate_journals.feature`): `test_lodgement_deposit_companion`, `test_lodgement_trading_companion`, `test_lodgement_idempotent`
  - New `@then` step: `"the journal contains a row with action {action} and reference {reference}"` — reads the output Excel journal, checks that at least one row matches both the action string and the reference string
  - New `@then` step: `"the journal contains exactly {n:d} rows"` — reads the output Excel journal, asserts `len(df) == n`
  - New `@when` step: `"I run consolidate_journals with method HL and account {account} again"` — repeats the same pipeline invocation for the idempotency scenario (reuses existing directory state); this step is required for BDD Scenario 3

- [X] T006 [US1] Confirm all 27 new tests fail (RED phase): run `python -m pytest tests/unit/consolidate_journals/test_offset_generator.py -k "lodgement" -v` and `python -m pytest tests/unit/consolidate_journals/test_journal_store.py -k "lodgement" -v` and `python -m pytest tests/features/steps/consolidate_journals_steps.py -k "lodgement_deposit_companion or lodgement_trading_companion or lodgement_idempotent" -v` — all must fail with `AttributeError`, `AssertionError`, or `ImportError` (no false passes)

**Checkpoint**: 26 tests written and confirmed failing. Implementation can now begin.

### Implementation for User Story 1

- [X] T007 [P] [US1] Extend `src/modes/consolidate_journals/offset_generator.py`:
  1. Add `DEPOSIT_SUFFIX` to the import from `constants`
  2. Add `_make_lodgement_deposit(self, event: JournalEvent) -> JournalEvent` private method: `action=DEPOSIT`, `sub_account=CASH_SUB_ACCOUNT`, `reference=event.reference + DEPOSIT_SUFFIX`, `value=-event.value`, `quantity=None`
  3. Add `_make_lodgement_trading(self, event: JournalEvent) -> JournalEvent` private method: `action=TRADING`, `sub_account=CASH_SUB_ACCOUNT`, `reference=event.reference + OFFSET_SUFFIX`, `value=event.value`, `quantity=None`
  4. Replace the list comprehension in `generate()` with an explicit loop that calls `_make_offset(e)` for BUY/SELL/DIVIDEND and **appends `_make_lodgement_deposit(e)` first then `_make_lodgement_trading(e)` second** for LODGEMENT (deposit companion is always index 0 of the pair; trading companion is always index 1)
  5. Update docstring on class and `generate()` to mention lodgement

- [X] T008 [P] [US1] Extend `src/modes/consolidate_journals/journal_store.py`:
  1. Add `RE_LODGEMENT` and `DEPOSIT_SUFFIX` to the import from `constants`
  2. Extend `_is_transaction_reference()` to return `True` for `RE_LODGEMENT.match(reference)` and `reference.endswith(DEPOSIT_SUFFIX)`
  3. Extend `missing_offset_trades()`: after the existing buy/sell/dividend check, add a lodgement check — build `existing_deposit_refs` from rows where `action == DEPOSIT`, then `needs_lodgement_companion = lodgement_mask & (~has_offset | ~has_deposit)` where `has_offset` checks `{ref}-offset` in `existing_trading_refs` and `has_deposit` checks `{ref}-deposit` in `existing_deposit_refs`; return `df[needs_trading_offset | needs_lodgement_companion].copy()`

- [X] T009 [US1] Confirm all 27 new tests pass (GREEN phase): run `python -m pytest tests/unit/consolidate_journals/test_offset_generator.py tests/unit/consolidate_journals/test_journal_store.py tests/features/ -v` — all new tests must pass; existing tests must not regress

**Checkpoint**: User Story 1 fully implemented and all tests green. Feature 013 functionality is complete.

---

## Phase 3: Polish & Quality Gates

**Purpose**: Mandatory quality gates per the project constitution (all four must be green before
the feature is considered done).

- [X] T010 [P] Run `mypy --strict src/` — zero errors required (Constitution gate III); fix any type annotation gaps in the three modified source files
- [X] T011 [P] Run `ruff check .` and `ruff format --check .` — zero violations required (Constitution gate IV); fix any style issues introduced by T007/T008
- [X] T012 Run full test suite `python -m pytest` — zero regressions across all 27+ new tests and all pre-existing tests; verify total test count increased by exactly 27 from the Feature 012 baseline (366 → 393)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 Tests (T002–T005)**: Depends on T001 (DEPOSIT_SUFFIX must exist to import in tests)
  - T002, T003, T004 can all run in parallel (different files)
  - T005 depends on T004 (step definitions must match scenario text)
  - T006 depends on T002, T003, T004, T005 (confirm failure of all new tests)
- **Phase 2 Implementation (T007–T008)**: Depends on T006 (must confirm RED before going GREEN)
  - T007 and T008 can run in parallel (different files, no mutual dependency)
- **T009**: Depends on T007 AND T008 (both source files must be complete before green confirmation)
- **Phase 3 (T010–T012)**: Depends on T009

### Parallel Opportunities

| Parallel Group | Tasks | Files |
|----------------|-------|-------|
| Test writing | T002, T003, T004 | 3 different files |
| Implementation | T007, T008 | 2 different files |
| Quality gates | T010, T011 | Independent tools |

---

## Implementation Strategy

### MVP (Single Story — Feature 013 is already a single increment)

1. T001: Add constant
2. T002–T005: Write all tests (in parallel where marked [P])
3. T006: Confirm RED
4. T007–T008: Implement (in parallel)
5. T009: Confirm GREEN
6. T010–T012: Quality gates

Total tasks: 12 | Test tasks: 5 (T002–T006, 27 new tests: 16 unit offset + 8 unit store + 3 BDD) | Implementation tasks: 3 (T007–T009) | Polish: 3 (T010–T012) | Setup: 1 (T001)

---

## Notes

- `valid_hl_lodgement.csv` fixture already exists from Feature 012 with 2 lodgement rows (L003538235 and L003538236). The idempotency scenario (T004 Scenario 3) expects exactly 6 rows: 2 lodgements + 2 deposit companions + 2 trading companions.
- `_is_transaction_reference` is a module-level private function in `journal_store.py`. Tests for it should call it directly (import from the module using `from src.modes.consolidate_journals.journal_store import _is_transaction_reference`).
- The `generate()` method in `offset_generator.py` must remain backward-compatible: existing buy/sell/dividend tests must continue to pass unchanged (verify via T009 regression run).
- T008 variable naming: rename the existing `existing_offset_refs` variable to `existing_trading_refs` inside `missing_offset_trades()` for clarity when both deposit and trading ref sets are present.
- **FR-007 coverage**: No targeted test verifies that existing buy/sell/dividend rows are unchanged after lodgement companion generation. This is a known gap — the T009/T012 full-suite regression passes provide sufficient implicit coverage. If a targeted test is desired, add it to `TestLodgementDedup`: load a store with a buy row plus a lodgement; after generating companions, assert the buy row is unmodified.
- **Companion ordering in `generate()`**: `_make_lodgement_deposit` is always appended before `_make_lodgement_trading` within a single lodgement iteration. Tests that rely on action-based lookup (using `any(...)`) are preferred over index-based access to be robust against future reordering.
