---
description: "Task list for income dividend action mappings feature"
---

# Tasks: Income Dividend Action Mappings

**Input**: Design documents from `specs/009-income-dividend-mappings/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

**Tests**: Tests are MANDATORY per the project constitution. Every user story includes Gherkin BDD
scenarios (`tests/features/consolidate_journals.feature`) and `pytest` unit tests
(`tests/unit/consolidate_journals/parsers/test_hl_parser.py`). Tests MUST be written and confirmed
FAILING before implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.
Each story adds exactly one new reference→action mapping, building on the shared infrastructure
created in US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup (Verify Prerequisites)

**Purpose**: Confirm the development environment is ready before making any changes.

- [X] T001 Activate virtual environment (`.venv`) and confirm `pytest`, `mypy`, and `ruff` are available; run `python -m pytest tests/` and confirm all pre-existing tests pass as the regression baseline

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Add `ActionType.DIVIDEND` to the enum — every user story depends on this value existing before constants, the helper function, or tests can compile.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `DIVIDEND = "dividend"` to the `ActionType` `StrEnum` in `src/modes/consolidate_journals/schema.py` (insert after the `TRADING` member; `DIVIDEND` must NOT be added to `CASH_ACTION_TYPES` in constants.py)

**Checkpoint**: `python -c "from src.modes.consolidate_journals.schema import ActionType; print(ActionType.DIVIDEND)"` must print `dividend`.

---

## Phase 3: User Story 1 — ST DIV Dividend Payment Mapping (Priority: P1) 🎯 MVP

**Goal**: Map `"ST DIV"` reference to `ActionType.DIVIDEND`; derive sub-account by stripping `" Dividend Payment"` from description. Also establishes the shared infrastructure (`HL_DIVIDEND_REFERENCES`, `HL_DIVIDEND_SUFFIX_MAP`, `_strip_dividend_suffix`, `_parse_row` `elif` branch) that all later stories extend.

**Independent Test**: Parse `tests/data/consolidate_journals/valid_hl_st_div.csv` — must produce `dividend` events with sub-account `"Barclays plc Ordinary 25p"` and zero parse errors.

### Tests for US1 ⚠️ (Write FIRST — confirm FAILING before implementing)

- [X] T003 [P] [US1] Add BDD scenario `Maps ST DIV reference to dividend action` in `tests/features/consolidate_journals.feature` (Given fragment with ST DIV row / When consolidate_journals runs / Then journal contains dividend event with holding-name sub-account)
- [X] T004 [P] [US1] Create test fixture `tests/data/consolidate_journals/valid_hl_st_div.csv` with two ST DIV rows (different holdings) matching the format in `quickstart.md`
- [X] T005 [P] [US1] Add unit tests to `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: `test_st_div_reference_maps_to_dividend` (in `TestActionMapping`); and in new class `TestDividendSubAccount`: `test_st_div_sub_account_strips_dividend_payment_suffix`, `test_st_div_fallback_when_suffix_absent` (description without expected suffix → full description returned, FR-009), `test_st_div_fallback_when_description_equals_suffix_only` (description equals exactly the suffix → reference string returned, FR-009 edge case); run tests and confirm they FAIL before proceeding

### Implementation for US1

- [X] T006 [US1] Add `HL_DIVIDEND_REFERENCES: frozenset[str] = frozenset({"ST DIV"})` and `HL_DIVIDEND_SUFFIX_MAP: dict[str, tuple[str, ...]] = {"ST DIV": (" Dividend Payment",)}` to `src/modes/consolidate_journals/constants.py`
- [X] T007 [US1] Add `_strip_dividend_suffix(reference: str, description: str) -> str` helper function to `src/modes/consolidate_journals/parsers/hl.py`: for non-LOYALTYU references, look up suffix tuple in `HL_DIVIDEND_SUFFIX_MAP`, strip first matching suffix, return `result or description or reference`; update imports to include `HL_DIVIDEND_REFERENCES`, `HL_DIVIDEND_SUFFIX_MAP` from constants
- [X] T008 [US1] Extend `_map_action()` in `src/modes/consolidate_journals/parsers/hl.py`: add `if ref.upper() in HL_DIVIDEND_REFERENCES: return ActionType.DIVIDEND` before the final `raise ValueError`
- [X] T009 [US1] Extend `_parse_row()` in `src/modes/consolidate_journals/parsers/hl.py`: add `elif action is ActionType.DIVIDEND: sub_account = _strip_dividend_suffix(reference, description)` branch between the `CASH_ACTION_TYPES` check and the existing `else` block
- [X] T010 [US1] Run ST DIV tests and confirm all pass; run full test suite to confirm zero regressions

**Checkpoint**: `valid_hl_st_div.csv` parses to two `dividend` events with correct sub-accounts; all pre-existing tests green.

---

## Phase 4: User Story 2 — OVR CR Overseas Dividend Mapping (Priority: P1)

**Goal**: Extend `HL_DIVIDEND_REFERENCES` and `HL_DIVIDEND_SUFFIX_MAP` to cover `"OVR CR"`; sub-account is description minus `" Overseas Dividend Payment"`. No changes to `hl.py` needed — the infrastructure from US1 handles it.

**Independent Test**: Parse `tests/data/consolidate_journals/valid_hl_ovr_cr.csv` — must produce `dividend` events with sub-account `"Man Group plc ORD USD0.0342857142"` and zero parse errors.

### Tests for US2 ⚠️ (Write FIRST — confirm FAILING before implementing)

- [X] T011 [P] [US2] Add BDD scenario `Maps OVR CR reference to dividend action` in `tests/features/consolidate_journals.feature`
- [X] T012 [P] [US2] Create test fixture `tests/data/consolidate_journals/valid_hl_ovr_cr.csv` with two OVR CR rows matching real data in `quickstart.md`
- [X] T013 [P] [US2] Add unit tests to `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: `test_ovr_cr_reference_maps_to_dividend` and `test_ovr_cr_sub_account_strips_overseas_dividend_payment_suffix`; confirm FAILING

### Implementation for US2

- [X] T014 [US2] Add `"OVR CR"` to `HL_DIVIDEND_REFERENCES` and add entry `"OVR CR": (" Overseas Dividend Payment",)` to `HL_DIVIDEND_SUFFIX_MAP` in `src/modes/consolidate_journals/constants.py`
- [X] T015 [US2] Run OVR CR tests and confirm all pass; run full test suite to confirm zero regressions

**Checkpoint**: `valid_hl_ovr_cr.csv` parses with correct sub-accounts; US1 and US2 tests both green.

---

## Phase 5: User Story 3 — UTC CR Unit Trust Cash Payment Mapping (Priority: P2)

**Goal**: Extend constants to cover `"UTC CR"`; two suffix variants (`" Eql - UT Cash Payment"` and `" UT Cash Payment"`) must be tried in order — longer suffix first. No changes to `hl.py` needed.

**Independent Test**: Parse `tests/data/consolidate_journals/valid_hl_utc_cr.csv` (containing one row of each suffix variant) — must produce two `dividend` events with identical sub-account `"HSBC FTSE 250 Index Class S - Income (GBP)"` and zero parse errors.

### Tests for US3 ⚠️ (Write FIRST — confirm FAILING before implementing)

- [X] T016 [P] [US3] Add BDD scenario `Maps UTC CR reference to dividend action` in `tests/features/consolidate_journals.feature` (covering both suffix variants)
- [X] T017 [P] [US3] Create test fixture `tests/data/consolidate_journals/valid_hl_utc_cr.csv` with one `Eql - UT Cash Payment` row and one `UT Cash Payment` row (same fund name, different suffixes)
- [X] T018 [P] [US3] Add unit tests to `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: `test_utc_cr_reference_maps_to_dividend`, `test_utc_cr_eql_suffix_stripped`, `test_utc_cr_plain_suffix_stripped`; confirm FAILING

### Implementation for US3

- [X] T019 [US3] Add `"UTC CR"` to `HL_DIVIDEND_REFERENCES` and add entry `"UTC CR": (" Eql - UT Cash Payment", " UT Cash Payment")` to `HL_DIVIDEND_SUFFIX_MAP` in `src/modes/consolidate_journals/constants.py` (longer suffix first in tuple — ensures `" Eql -"` is not left in the sub-account)
- [X] T020 [US3] Run UTC CR tests and confirm all pass; run full test suite to confirm zero regressions

**Checkpoint**: Both UTC CR suffix variants produce the same clean fund-name sub-account; US1–US3 tests all green.

---

## Phase 6: User Story 4 — LOYALTYU Gross Loyalty Payment Mapping (Priority: P2)

**Goal**: Extend constants to cover `"LOYALTYU"` with a compiled regex for the dynamic `" MM YY Gross Loyalty"` suffix. Extend `_strip_dividend_suffix()` to add the LOYALTYU branch: raises `ValueError` (FR-008A) if pattern does not match, strips if it does.

**Independent Test**: Parse `tests/data/consolidate_journals/valid_hl_loyaltyu.csv` (3 rows with different month-year values) — all must produce `dividend` events with the same fund-name sub-account and zero parse errors. Calling `_strip_dividend_suffix("LOYALTYU", "Fund 4 26 Gross Loyalty")` directly must raise `ValueError`.

### Tests for US4 ⚠️ (Write FIRST — confirm FAILING before implementing)

- [X] T021 [P] [US4] Add BDD scenario `Maps LOYALTYU reference to dividend action` in `tests/features/consolidate_journals.feature` (spanning at least 3 different month-year values)
- [X] T022 [P] [US4] Create test fixture `tests/data/consolidate_journals/valid_hl_loyaltyu.csv` with three LOYALTYU rows: `04 26`, `01 26`, `07 25` (same fund, different months) matching `quickstart.md`
- [X] T023 [P] [US4] Add unit tests to `tests/unit/consolidate_journals/parsers/test_hl_parser.py`: `test_loyaltyu_reference_maps_to_dividend`, `test_loyaltyu_sub_account_strips_04_26_suffix`, `test_loyaltyu_sub_account_strips_01_26_suffix`, `test_loyaltyu_sub_account_strips_07_25_suffix`, `test_loyaltyu_non_matching_pattern_raises_value_error` (single-digit month `" 4 26 Gross Loyalty"`); confirm FAILING

### Implementation for US4

- [X] T024 [US4] Add `"LOYALTYU"` to `HL_DIVIDEND_REFERENCES` and add `RE_LOYALTYU_SUFFIX: re.Pattern[str] = re.compile(r" \d{2} \d{2} Gross Loyalty$")` to `src/modes/consolidate_journals/constants.py`
- [X] T025 [US4] Extend `_strip_dividend_suffix()` in `src/modes/consolidate_journals/parsers/hl.py`: add `if ref_upper == "LOYALTYU":` branch — call `RE_LOYALTYU_SUFFIX.search(description)`; if no match raise `ValueError(f"LOYALTYU description does not match expected '\\d{{2}} \\d{{2}} Gross Loyalty' pattern: {description!r}")`; otherwise strip with `RE_LOYALTYU_SUFFIX.sub("", description).strip()`; import `RE_LOYALTYU_SUFFIX` from constants
- [X] T026 [US4] Run LOYALTYU tests and confirm all pass (including the `ValueError` case); run full test suite to confirm zero regressions

**Checkpoint**: All four reference types map to `dividend` with correct sub-accounts; LOYALTYU error case confirmed; US1–US4 tests all green.

---

## Phase 7: User Story 5 — End-to-End Zero Dropped Rows (Priority: P3)

**Goal**: Confirm that running `consolidate_journals` against all 8 historical HL ISA Income Account fragment files produces zero parse errors and retains 100% of rows.

**Independent Test**: Summary output reports `ERRORS: None`; row count in output equals total data rows across all 8 fragment files.

- [X] T027 [US5] Run `consolidate_journals` against all fragment files in `C:\Users\jhoxl\OneDrive\Investments\Journals\HL Stocks and Shares ISA - Income Account` and verify the summary reports zero errors and zero dropped rows
- [X] T028 [US5] Inspect the `action` column of the consolidated journal output — verify every row has a known action value (`buy`, `sell`, `deposit`, `income`, `fee`, `withdrawal`, `trading`, or `dividend`) and no null or unrecognised values appear
- [X] T029 [US5] Visually inspect `sub_account` values for `dividend` rows against known holdings in the capital account data to confirm sub-accounts match (SC-003); note any mismatches for investigation

**Checkpoint**: 100% of income account rows retained; all dividend sub-accounts produce valid holding-name joins.

---

## Phase 8: Polish & Quality Gates

**Purpose**: All four constitution quality gates must be green before this feature is considered complete.

- [X] T030 [P] Run `mypy --strict src/` — must report zero errors (Constitution gate III)
- [X] T031 [P] Run `ruff check .` and `ruff format --check .` — must both report zero violations (Constitution gate IV)
- [X] T032 Run full test suite `python -m pytest tests/ -v` — must report zero failures; confirm test count has increased by the expected number of new tests (Constitution gate I)
- [X] T033 Verify new `dividend` events appear in existing "HL parse complete" debug log at the correct event count when processing a test fixture; confirm no `print()` statements appear in any changed source file — Constitution gate 4 (Observability)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1; **BLOCKS all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2 — establishes shared infrastructure; BLOCKS no other story but provides it
- **Phase 4 (US2)**: Depends on Phase 3 (needs `HL_DIVIDEND_REFERENCES` frozenset and `_strip_dividend_suffix` to exist)
- **Phase 5 (US3)**: Depends on Phase 3 (same reason); can run in parallel with Phase 4 on different files
- **Phase 6 (US4)**: Depends on Phase 3 (needs to extend the existing function)
- **Phase 7 (US5)**: Depends on Phases 3–6 all complete
- **Phase 8 (Polish)**: Depends on Phase 7

### Within Each User Story

1. Create test fixture (CSV) — no dependencies, can do first
2. Write BDD scenario and unit tests — no dependencies on implementation
3. **Confirm tests FAIL** — before writing any implementation
4. Update constants.py — no hl.py dependency
5. Update hl.py (where applicable) — depends on constants
6. Confirm tests pass + run regression suite

### Parallel Opportunities

| Phase | Parallelisable tasks |
|-------|----------------------|
| Phase 3 | T003, T004, T005 can run together (different files) |
| Phase 4 | T011, T012, T013 can run together |
| Phase 5 | T016, T017, T018 can run together |
| Phase 6 | T021, T022, T023 can run together |
| Phase 8 | T030 and T031 can run together |

---

## Parallel Example: User Story 1

```bash
# Step 1 — create tests and fixture together:
Task T003: Add BDD scenario to tests/features/consolidate_journals.feature
Task T004: Create tests/data/consolidate_journals/valid_hl_st_div.csv
Task T005: Add unit tests to test_hl_parser.py

# Step 2 — confirm tests FAIL (required gate before Step 3):
python -m pytest tests/ -k "st_div" -v  # expect FAIL

# Step 3 — implement (sequential, same file hl.py):
Task T006: Update constants.py
Task T007: Add _strip_dividend_suffix() to hl.py
Task T008: Extend _map_action() in hl.py
Task T009: Extend _parse_row() in hl.py

# Step 4 — confirm tests pass:
Task T010: python -m pytest tests/ -v
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 — confirm baseline
2. T002 — add `DIVIDEND` to schema (**critical blocker**)
3. T003–T005 — write ST DIV tests, confirm FAIL
4. T006–T009 — implement ST DIV mapping + shared infrastructure
5. T010 — confirm ST DIV tests pass + no regressions
6. **STOP and VALIDATE**: `valid_hl_st_div.csv` produces correct events independently

### Incremental Delivery

Each subsequent story (US2–US4) follows the same test-first pattern and requires only constants.py changes (plus a `_strip_dividend_suffix` extension for US4). The hl.py changes made in US1 transparently handle all subsequent stories once their references are in `HL_DIVIDEND_REFERENCES`.

---

## Notes

- [P] = different files, no inter-task dependency — safe to run in parallel
- `HL_DIVIDEND_REFERENCES` grows one entry per user story (US1 → US4); final state matches data-model.md
- LOYALTYU (US4) is the only story requiring an hl.py change beyond US1 (the `_strip_dividend_suffix` LOYALTYU branch + `ValueError`)
- The integration test (Phase 7) is manual/local only — the real income fragment files are not in the repo
- All sub-account values must match capital account holding names exactly — verify with SC-003 during T029
