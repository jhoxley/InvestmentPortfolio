# Tasks: HL Action Mapping â€” Card Web, FPC, Commission

**Input**: Design documents from `specs/008-hl-action-mapping/`
**Prerequisites**: plan.md âœ“, spec.md âœ“, research.md âœ“, data-model.md âœ“, quickstart.md âœ“

**Tests**: Tests are MANDATORY per the project constitution. Every user story MUST include Gherkin
BDD feature files (`tests/features/`) and `pytest` unit tests (`tests/unit/`). Tests MUST be
written and confirmed failing BEFORE implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project structure required. Source and test directories (`src/`, `tests/`) are already in place.

*No tasks â€” project infrastructure is fully in place. Proceed to Phase 3.*

---

## Phase 2: Foundational

**Purpose**: No shared blocking prerequisites across user stories. All three reference mappings are additive changes to the same two source files; each user story's tests and implementation are independently startable.

*No tasks â€” user story phases can begin immediately.*

---

## Phase 3: User Story 1 â€” Card Web and FPC Deposit References (Priority: P1) ðŸŽ¯ MVP

**Goal**: Parse `"Card Web"` and `"FPC"` references (case-insensitive, exact match after whitespace trim) as `deposit` events with `sub_account = "Cash"` â€” zero parse errors.

**Independent Test**:
```powershell
python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py -k "card_web or fpc" -v
python -m pytest tests/features/ -k "Card Web" -v
```

### Tests for User Story 1 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementation)

- [x] T001 [P] [US1] Create CSV fixture `tests/data/consolidate_journals/valid_hl_card_web.csv` â€” two rows: reference `"Card Web"` settle date `15/03/2024`, value `500.00`, description `"Card payment deposit"`; and reference `"card web"` settle date `16/03/2024`, value `250.00`; header: `Trade date,Settle date,Reference,Description,Unit cost (Â£),Qty,Value (Â£)`
- [x] T002 [P] [US1] Create CSV fixture `tests/data/consolidate_journals/valid_hl_fpc.csv` â€” two rows: reference `"FPC"` settle date `20/03/2024`, value `1000.00`, description `"FPC transfer"`; and reference `"fpc"` settle date `21/03/2024`, value `750.00`; same header as above
- [x] T003 [P] [US1] Add 2 BDD scenarios to `tests/features/consolidate_journals.feature`: `"Maps Card Web reference to deposit action"` (uses `valid_hl_card_web.csv`, asserts both rows produce `action=deposit`, `sub_account=Cash`, zero parse errors) and `"Maps FPC reference to deposit action"` (uses `valid_hl_fpc.csv`, same assertions). Before writing scenarios, verify that existing parameterised step definitions in `tests/features/steps/consolidate_journals_steps.py` accept the new fixture CSV names; if not, extend step definitions in the same task.
- [x] T004 [P] [US1] Add 8 unit tests in `TestActionMapping` class in `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: `test_card_web_reference_maps_to_deposit`, `test_card_web_reference_is_case_insensitive` (uses `"CARD WEB"` and `"card web"`), `test_card_web_sub_account_is_cash`, `test_fpc_reference_maps_to_deposit`, `test_fpc_reference_is_case_insensitive` (uses `"fpc"`), `test_fpc_sub_account_is_cash`; plus 2 boundary/coverage tests: `test_card_web_prefix_does_not_map_to_deposit` (call `_map_action("Card Web2", "")` and assert it raises `ValueError` â€” exact match only, spec edge-case #2) and `test_mixed_reference_file_parses_without_error` (parse an inline CSV with one `"Card Web"` row, one `"Deposit"` row, and one `"INTEREST"` row in a single call; assert all three produce events with zero errors â€” FR-008, spec edge-case #3)
- [x] T005 [US1] RED checkpoint â€” run `python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py -k "card_web or fpc" -v` and confirm all 8 new tests FAIL (expect `ValueError`/`ParseError`); run `python -m pytest tests/features/ -k "Card Web" -v` and confirm both new BDD scenarios FAIL

### Implementation for User Story 1

- [x] T006 [US1] Add `HL_DEPOSIT_REFERENCE_ALIASES: frozenset[str] = frozenset({"CARD WEB", "FPC"})` to `src/modes/consolidate_journals/constants.py` after the existing `HL_DEPOSIT_REFERENCES` constant; add `HL_DEPOSIT_REFERENCE_ALIASES` to the import in `src/modes/consolidate_journals/parsers/hl.py`
- [x] T007 [US1] Extend the deposit branch in `_map_action()` in `src/modes/consolidate_journals/parsers/hl.py` â€” change `if ref in HL_DEPOSIT_REFERENCES or ref.upper().startswith("BACS"):` to `if ref in HL_DEPOSIT_REFERENCES or ref.upper().startswith("BACS") or ref.upper() in HL_DEPOSIT_REFERENCE_ALIASES:`
- [x] T008 [US1] GREEN checkpoint â€” run `python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py tests/features/ -v`; confirm all 6 US1 unit tests pass and both BDD scenarios pass; confirm all pre-existing tests still pass (zero regressions)

**Checkpoint**: User Story 1 complete â€” `"Card Web"` and `"FPC"` (any case) produce deposit events with no parse errors.

---

## Phase 4: User Story 2 â€” Commission Income Reference (Priority: P2)

**Goal**: Parse `"Commission"` references (case-insensitive, exact match after whitespace trim) as `income` events with `sub_account = "Cash"` â€” zero parse errors. Simultaneously consolidates existing `"INTEREST"` / `"RDP CR"` magic strings into a named constant.

**Independent Test**:
```powershell
python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py -k "commission" -v
python -m pytest tests/features/ -k "Commission" -v
```

### Tests for User Story 2 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementation)

- [x] T009 [P] [US2] Create CSV fixture `tests/data/consolidate_journals/valid_hl_commission.csv` â€” two rows: reference `"Commission"` settle date `10/04/2024`, value `12.50`, description `"Commission rebate"`; and reference `"COMMISSION"` settle date `11/04/2024`, value `8.75`, description `"Commission rebate annual"`; same header as US1 fixtures
- [x] T010 [P] [US2] Add 1 BDD scenario to `tests/features/consolidate_journals.feature`: `"Maps Commission reference to income action"` â€” uses `valid_hl_commission.csv`, asserts both rows produce `action=income`, `sub_account=Cash`, zero parse errors. Before writing, verify existing step definitions in `tests/features/steps/consolidate_journals_steps.py` accept the new fixture file name; extend step definitions in the same task if needed.
- [x] T011 [P] [US2] Add 3 unit tests in `TestActionMapping` class in `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: `test_commission_reference_maps_to_income`, `test_commission_reference_is_case_insensitive` (uses `"COMMISSION"` and `"commission"`), `test_commission_sub_account_is_cash`
- [x] T012 [US2] RED checkpoint â€” run `python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py -k "commission" -v` and confirm all 3 new tests FAIL; run BDD suite and confirm the new Commission scenario FAILS

### Implementation for User Story 2

- [x] T013 [US2] Add `HL_INCOME_REFERENCES: frozenset[str] = frozenset({"INTEREST", "RDP CR", "COMMISSION"})` to `src/modes/consolidate_journals/constants.py` after `HL_DEPOSIT_REFERENCE_ALIASES`; add `HL_INCOME_REFERENCES` to the import in `src/modes/consolidate_journals/parsers/hl.py`
- [x] T014 [US2] In `_map_action()` in `src/modes/consolidate_journals/parsers/hl.py`, replace `if ref.upper() in ("INTEREST", "RDP CR"):` with `if ref.upper() in HL_INCOME_REFERENCES:` â€” this adds Commission support and eliminates the existing magic strings in one change
- [x] T015 [US2] GREEN checkpoint â€” run `python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py tests/features/ -v`; confirm all 3 US2 tests pass, the Commission BDD scenario passes, and existing `INTEREST` / `RDP CR` tests still pass (zero regressions)

**Checkpoint**: User Story 2 complete â€” `"Commission"` (any case) produces income events; `"INTEREST"` and `"RDP CR"` continue to work unchanged via `HL_INCOME_REFERENCES`.

---

## Phase 5: User Story 3 â€” End-to-End Pipeline Success on HL ISA Fragments (Priority: P3)

**Goal**: Zero parse errors and zero dropped rows when running the full pipeline (`consolidate_journals` then `create_ledger`) against the real HL ISA transaction fragment CSV files.

**Note**: This is a manual/local-only acceptance step. The HL ISA fragment files live at `C:\Users\jhoxl\OneDrive\Investments\Journals\HL Stocks and Shares ISA - Capital Account` and are not committed to the repository. US1 and US2 implementation (T006â€“T007, T013â€“T014) must be complete before running these steps.

- [ ] T016 [US3] Run `python pipeline.py consolidate_journals "C:\Users\jhoxl\OneDrive\Investments\Journals\HL Stocks and Shares ISA - Capital Account" <output_journal.xlsx>` â€” verify exit code is 0, output log reports zero parse errors, and the output row count equals the total input rows summed across all fragment CSVs (FR-009, SC-002)
- [ ] T017 [US3] Run `python pipeline.py create_ledger <output_journal.xlsx> <output_ledger.xlsx>` â€” verify exit code is 0, ledger row count equals journal row count, and `Transaction ID` column is populated for every row

**Checkpoint**: US3 complete â€” full pipeline processes real HL ISA data end-to-end with no dropped rows.

---

## Phase 6: Polish & Quality Gates

**Purpose**: Mandatory constitution quality gates across all changes in `constants.py` and `hl.py`.

- [x] T018 [P] Run `mypy --strict src/` from repo root â€” zero type errors required (Constitution gate III); the two new frozenset constants and the modified `_map_action()` branch must be fully type-annotated
- [x] T019 [P] Run `ruff check . --fix` then `ruff format .` from repo root â€” zero remaining violations required (Constitution gate IV)
- [x] T020 Run full test suite `python -m pytest tests/features/ tests/unit/ tests/integration/ -v --tb=short` â€” zero failures across BDD scenarios, unit tests, and integration tests; confirms no regressions across all pipeline modes (Constitution Â§V requires all Gherkin scenarios and unit tests to pass)
- [x] T021 Explicit regression check: run `python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py tests/features/ -v` and verify all pre-existing `TestActionMapping` unit tests and all pre-existing BDD scenarios still pass (SC-004, FR-007)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: N/A
- **Foundational (Phase 2)**: N/A â€” all user story phases can start immediately
- **US1 (Phase 3)**: No dependencies â€” start immediately
- **US2 (Phase 4)**: Test tasks T009â€“T011 can be written in parallel with US1; implementation T013â€“T014 requires US1 implementation complete (T007 done) so the import context in `hl.py` is stable
- **US3 (Phase 5)**: Requires US1 implementation (T006â€“T007) AND US2 implementation (T013â€“T014) both complete
- **Polish (Phase 6)**: Requires all implementation tasks complete (T006, T007, T013, T014)

### User Story Dependencies

- **US1 (P1)**: Independent â€” start immediately
- **US2 (P2)**: Test tasks parallel with US1 implementation; implementation tasks sequential after US1 implementation
- **US3 (P3)**: Depends on US1 + US2 implementation complete

### Within Each User Story

- Fixture creation [P] tasks (T001â€“T002, T009) â†’ BDD + unit test tasks [P] (T003â€“T004, T010â€“T011) â†’ RED checkpoint â†’ constants addition â†’ parser extension â†’ GREEN checkpoint
- Constants file (T006/T013) must precede parser file (T007/T014) because the import must exist before the branch references it

### Parallel Opportunities

- T001, T002, T003, T004 â€” all different files, run in parallel
- T009, T010, T011 â€” all different files, run in parallel
- T009â€“T011 can start while T006â€“T008 (US1 implementation) is in progress
- T018, T019 â€” independent quality checks, run in parallel

---

## Parallel Example: User Story 1

```powershell
# Launch all test creation tasks together (T001-T004 are independent files):
# T001: tests/data/consolidate_journals/valid_hl_card_web.csv
# T002: tests/data/consolidate_journals/valid_hl_fpc.csv
# T003: tests/features/consolidate_journals.feature (new scenarios)
# T004: tests/unit/consolidate_journals/parsers/test_hl_parser.py (new tests)

# After RED confirmed (T005), run sequentially:
# T006: src/modes/consolidate_journals/constants.py (add HL_DEPOSIT_REFERENCE_ALIASES)
# T007: src/modes/consolidate_journals/parsers/hl.py (extend _map_action deposit branch)
# T008: GREEN checkpoint
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3 (T001â€“T008)
2. **STOP and VALIDATE**: All Card Web + FPC tests green, zero regressions
3. Proceed to US2 when ready

### Incremental Delivery

1. US1 (T001â€“T008) â†’ Card Web + FPC deposit events working
2. US2 (T009â€“T015) â†’ Commission income events working; magic-string refactor done
3. US3 (T016â€“T017) â†’ Real HL ISA data processes end-to-end with zero dropped rows
4. Polish (T018â€“T021) â†’ All quality gates pass, full suite clean

---

## Notes

- [P] tasks operate on different files with no shared dependencies â€” safe to run concurrently
- Constitution mandates TDD: tests must be written first and confirmed failing before any implementation
- US3 tasks (T016â€“T017) are manual/local-only steps; no automated test is created for them
- After T007 the deposit branch reads: `if ref in HL_DEPOSIT_REFERENCES or ref.upper().startswith("BACS") or ref.upper() in HL_DEPOSIT_REFERENCE_ALIASES:`
- After T014 the income branch reads: `if ref.upper() in HL_INCOME_REFERENCES:` (replaces the hardcoded `("INTEREST", "RDP CR")` tuple)
- `HL_INCOME_REFERENCES` consolidating existing magic strings is a constitution compliance fix bundled with the Commission addition â€” not a separate refactor task
